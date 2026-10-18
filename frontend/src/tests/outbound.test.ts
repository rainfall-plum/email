import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessage, ElMessageBox, ElPagination, ElSelect, ElForm } from 'element-plus'
import OutboundCompose from '../views/OutboundCompose.vue'
import OutboundRecords from '../views/OutboundRecords.vue'
import { outboundApi } from '../api'
import { useTheme } from '../utils/theme'
import { validateOutbound } from '../utils/outbound'

const push = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({ useRouter: () => ({ push }), useRoute: () => ({ query: { sender: '1' } }) }))
vi.mock('../api', () => ({ outboundApi: { options: vi.fn(), create: vi.fn(), list: vi.fn(), get: vi.fn(), retry: vi.fn() }, getApiErrorMessage: (_: unknown, fallback: string) => fallback }))
const record = { id: 1, sender_mailbox_id: 1, sender: 'sender@example.com', recipient: 'recipient@example.com', subject: '中文主题', body_text: '纯文本', status: 'failed' as const, attempt_count: 1, max_attempts: 5, last_error: '邮件服务拒绝接收', next_attempt_at: null, message_id: '<test@example.com>', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', sent_at: null, failed_at: null }
let wrapper: VueWrapper
function button(text: string) { return wrapper.findAll('button').find(item => item.text().includes(text))! }
async function compose() {
  wrapper = mount(OutboundCompose, { global: { plugins: [ElementPlus] }, attachTo: document.body })
  await flushPromises()
  const inputs = wrapper.findAll('input').filter(input => !input.classes().includes('el-select__input'))
  await inputs[0].setValue('recipient@example.com')
  await inputs[1].setValue('中文主题')
  await wrapper.find('textarea').setValue('纯文本')
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(outboundApi.options).mockResolvedValue([{ id: 1, email_address: 'sender@example.com' }])
  vi.mocked(outboundApi.create).mockResolvedValue(record)
  vi.mocked(outboundApi.list).mockResolvedValue({ items: [record], total: 42 })
  vi.mocked(outboundApi.get).mockResolvedValue(record)
  vi.mocked(outboundApi.retry).mockResolvedValue({ ...record, status: 'queued' })
  vi.spyOn(ElMessage, 'success').mockImplementation(() => ({ close: vi.fn() }))
  vi.spyOn(ElMessage, 'error').mockImplementation(() => ({ close: vi.fn() }))
})
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; vi.restoreAllMocks() })

describe('outbound compose', () => {
  it('rejects missing sender, blank text and oversized subject', () => {
    const draft = { sender_mailbox_id: undefined, recipient: '', subject: ' ', body_text: '\n', idempotency_key: 'test' }
    expect(Object.values(validateOutbound(draft)).every(Boolean)).toBe(true)
    expect(validateOutbound({ ...draft, subject: 'x'.repeat(201) }).subject).toContain('200')
  })
  it('renders plain text form and preselects the current mailbox', async () => {
    await compose()
    expect(wrapper.text()).toContain('仅支持纯文本，不支持 HTML 和附件')
    expect(wrapper.findComponent(ElSelect).props('modelValue')).toBe(1)
    expect(wrapper.find('input[type="file"]').exists()).toBe(false)
    await button('提交发送').trigger('click'); await flushPromises()
    expect(outboundApi.create).toHaveBeenCalledWith(expect.objectContaining({ sender_mailbox_id: 1, recipient: 'recipient@example.com', subject: '中文主题', body_text: '纯文本' }))
    expect(ElMessage.success).toHaveBeenCalledWith('发送任务已创建')
    expect(push).toHaveBeenCalledWith('/outbound')
  })
  it('validates a single recipient', async () => {
    await compose()
    await wrapper.findAll('input').filter(input => !input.classes().includes('el-select__input'))[0].setValue('bad,email')
    expect(wrapper.findComponent(ElForm).props('model')?.recipient).toBe('bad,email')
    await button('提交发送').trigger('click'); await flushPromises()
    await new Promise(resolve => setTimeout(resolve, 120))
    expect(wrapper.text()).toContain('请输入单个有效邮箱')
    expect(outboundApi.create).not.toHaveBeenCalled()
  })
  it('blocks duplicate submissions and shows loading', async () => {
    let resolve!: (value: typeof record) => void
    vi.mocked(outboundApi.create).mockImplementation(() => new Promise(done => { resolve = done }))
    await compose(); await button('提交发送').trigger('click'); await flushPromises()
    expect(button('确认原任务').classes()).toContain('is-loading')
    await button('确认原任务').trigger('click'); await flushPromises()
    expect(outboundApi.create).toHaveBeenCalledTimes(1)
    resolve(record); await flushPromises()
  })
  it('reuses the original idempotency key after an uncertain failure', async () => {
    vi.mocked(outboundApi.create).mockRejectedValueOnce(new Error('network'))
    await compose(); await button('提交发送').trigger('click'); await flushPromises()
    expect(ElMessage.error).toHaveBeenCalled()
    expect(wrapper.find('textarea').attributes('disabled')).toBeDefined()
    await button('确认原任务').trigger('click'); await flushPromises()
    expect(vi.mocked(outboundApi.create).mock.calls[0][0]).toEqual(vi.mocked(outboundApi.create).mock.calls[1][0])
  })
  it('offers retry after sender options fail', async () => {
    vi.mocked(outboundApi.options).mockRejectedValueOnce(new Error('network'))
    wrapper = mount(OutboundCompose, { global: { plugins: [ElementPlus] } }); await flushPromises()
    expect(wrapper.text()).toContain('发件邮箱加载失败')
    await button('重新加载').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('收件人')
  })
})

describe('outbound records', () => {
  async function records() { wrapper = mount(OutboundRecords, { global: { plugins: [ElementPlus] } }); await flushPromises() }
  it('supports pagination and status filtering', async () => {
    await records()
    wrapper.findComponent(ElPagination).vm.$emit('update:current-page', 2)
    wrapper.findComponent(ElPagination).vm.$emit('current-change', 2)
    await flushPromises()
    expect(outboundApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, page_size: 20 }), expect.any(AbortSignal))
    wrapper.findComponent(ElSelect).vm.$emit('update:modelValue', 'failed')
    wrapper.findComponent(ElSelect).vm.$emit('change', 'failed'); await flushPromises()
    expect(outboundApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, status: 'failed' }), expect.any(AbortSignal))
    wrapper.findComponent(ElPagination).vm.$emit('update:page-size', 50)
    wrapper.findComponent(ElPagination).vm.$emit('size-change', 50); await flushPromises()
    expect(outboundApi.list).toHaveBeenLastCalledWith(expect.objectContaining({ page_size: 50 }), expect.any(AbortSignal))
  })
  it('confirms and retries a failed email', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockImplementation(() => Promise.resolve('confirm') as ReturnType<typeof ElMessageBox.confirm>)
    await records(); await button('重试').trigger('click'); await flushPromises()
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(outboundApi.retry).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('已加入发送队列')
  })
  it('disables retry at five attempts', async () => {
    vi.mocked(outboundApi.list).mockResolvedValue({ items: [{ ...record, attempt_count: 5 }], total: 1 })
    await records()
    expect(button('重试').attributes('disabled')).toBeDefined()
  })
  it.each(['dark', 'white', 'paper', 'system'] as const)('keeps status text and controls in %s theme', async theme => {
    useTheme().setTheme(theme); await records()
    expect(document.documentElement.dataset.theme).toBe(theme)
    expect(wrapper.text()).toContain('发送失败')
    expect(wrapper.text()).toContain('邮件服务拒绝接收')
    expect(button('详情').exists()).toBe(true)
  })
})
