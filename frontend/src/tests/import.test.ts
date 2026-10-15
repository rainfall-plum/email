import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import UsernameImport from '../components/UsernameImport.vue'
import { mailboxApi, type ImportResult } from '../api'
import { IMPORT_EXAMPLE, IMPORT_MAX_BYTES, parseImport, validateImportFile } from '../utils/importUsernames'
import { useTheme } from '../utils/theme'
vi.mock('../api', () => ({ mailboxApi: { importUsernames: vi.fn() }, getApiErrorMessage: (_: unknown, fallback: string) => fallback }))
const result: ImportResult = { total: 4, success_count: 1, duplicate_count: 1, invalid_count: 1, existing_count: 1, created_mailboxes: [{ username: 'alice', email: 'alice@example.com', mailbox_id: 1 }], rejected_usernames: [{ username: 'alice', reason: 'duplicate_in_file', message: '文件内重复' }, { username: 'bad.name', reason: 'invalid_format', message: '用户名只能包含小写字母和数字' }, { username: 'existing', reason: 'already_exists', message: '邮箱已存在' }] }
let wrapper: VueWrapper
const button = (text: string) => wrapper.findAll('button').find(item => item.text().includes(text))!
function fixture(text: string, name = 'names.json') { const file = new File([text], name); Object.defineProperty(file, 'arrayBuffer', { configurable: true, value: async () => new TextEncoder().encode(text).buffer }); return file }
async function choose(file: File) { const input = wrapper.find('input[type="file"]'); Object.defineProperty(input.element, 'files', { configurable: true, value: [file] }); await input.trigger('change'); await flushPromises() }
async function open() { wrapper = mount(UsernameImport, { global: { plugins: [ElementPlus], stubs: { teleport: true } }, attachTo: document.body }); await button('上传用户名').trigger('click'); await flushPromises() }
beforeEach(() => { vi.clearAllMocks(); vi.mocked(mailboxApi.importUsernames).mockResolvedValue(result); vi.spyOn(ElMessage, 'success').mockImplementation(() => ({ close: vi.fn() })); vi.spyOn(ElMessage, 'error').mockImplementation(() => ({ close: vi.fn() })) })
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; vi.restoreAllMocks() })
describe('import validation', () => {
  it('accepts exactly the documented JSON example', () => expect(parseImport(IMPORT_EXAMPLE)).toEqual({ error: '', invalid: 0, total: 3 }))
  it.each(['{}', '[]', '{"usernames":"alice"}', '{"usernames":["alice"],"domain":"example.com"}', '{"usernames":[]}'])('rejects unsupported structure %s', text => expect(parseImport(text).error).not.toBe(''))
  it('rejects damaged JSON and excessive quantity', () => { expect(parseImport('{').error).toContain('解析失败'); expect(parseImport(JSON.stringify({ usernames: Array(1001).fill('alice') })).error).toContain('1000') })
  it('rejects extension and size while counting invalid usernames without normalization', () => {
    expect(validateImportFile(new File(['{}'], 'names.txt'))).toContain('.json')
    expect(validateImportFile(new File([new Uint8Array(IMPORT_MAX_BYTES + 1)], 'names.json'))).toContain('1 MiB')
    expect(validateImportFile(new File([], 'names.json'))).toContain('不能为空')
    expect(parseImport(JSON.stringify({ usernames: ['alice', '123', 'ab12', '大写', 'Alice', 'a.b', 'a-b', 'a_b', '', ' alice', 'a'.repeat(65), 1] })).invalid).toBe(9)
  })
})
describe('username upload component', () => {
  it('shows schema, field rules and downloads the example', async () => {
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:example'), revokeObjectURL: vi.fn() }))
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await open(); expect(wrapper.text()).toContain('usernames'); expect(wrapper.text()).toContain('1000'); expect(wrapper.text()).toContain('alicewang')
    await button('下载示例').trigger('click'); expect(click).toHaveBeenCalledTimes(1); expect(URL.createObjectURL).toHaveBeenCalled()
  })
  it('reports format, size, JSON and UTF-8 failures before upload', async () => {
    await open(); await choose(fixture('{}', 'bad.txt')); expect(wrapper.text()).toContain('请选择 .json')
    await choose(new File([new Uint8Array(IMPORT_MAX_BYTES + 1)], 'large.json')); expect(wrapper.text()).toContain('1 MiB')
    await choose(fixture('{')); expect(wrapper.text()).toContain('JSON 解析失败')
    const invalid = fixture('{}'); Object.defineProperty(invalid, 'arrayBuffer', { value: async () => new Uint8Array([255]).buffer })
    await choose(invalid); expect(wrapper.text()).toContain('UTF-8'); expect(mailboxApi.importUsernames).not.toHaveBeenCalled()
  })
  it('uploads, renders all rejection reasons, refreshes parent and allows another file', async () => {
    await open(); await choose(fixture('{"usernames":["alice","alice","bad.name","existing"]}'))
    expect(wrapper.text()).toContain('格式不合法'); await button('开始导入').trigger('click'); await flushPromises()
    expect(mailboxApi.importUsernames).toHaveBeenCalledTimes(1); expect(wrapper.emitted('imported')).toHaveLength(1)
    expect(wrapper.text()).toContain('导入结果'); expect(wrapper.text()).toContain('duplicate_in_file'); expect(wrapper.text()).toContain('bad.name'); expect(wrapper.text()).toContain('批量生成时才会创建邮箱')
    await button('重新上传').trigger('click'); expect(wrapper.text()).not.toContain('导入结果'); expect(button('开始导入').attributes('disabled')).toBeDefined()
  })
  it('locks the upload while pending and prevents duplicate submissions', async () => {
    let resolve!: (value: ImportResult) => void
    vi.mocked(mailboxApi.importUsernames).mockImplementation(() => new Promise(done => { resolve = done }))
    await open(); await choose(fixture(IMPORT_EXAMPLE)); await button('开始导入').trigger('click'); await button('开始导入').trigger('click')
    expect(mailboxApi.importUsernames).toHaveBeenCalledTimes(1); expect(button('开始导入').classes()).toContain('is-loading'); expect(wrapper.find('input[type="file"]').attributes('disabled')).toBeDefined()
    resolve(result); await flushPromises()
  })
  it('derives pool counters from each rejected item when aggregate optional fields are absent', async () => {
    vi.mocked(mailboxApi.importUsernames).mockResolvedValue({ ...result, total: 3, success_count: 0, duplicate_count: 0, invalid_count: 0, existing_count: 3, created_mailboxes: [], rejected_usernames: [{ username: 'alice', reason: 'already_available', message: '可用池已存在' }, { username: 'bob', reason: 'already_available', message: '可用池已存在' }, { username: 'carol', reason: 'already_used', message: '使用池已存在' }] })
    await open(); await choose(fixture(IMPORT_EXAMPLE)); await button('开始导入').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('已在用户名池：2')
  })
  it.each(['dark', 'white', 'paper', 'system'] as const)('keeps schema and accessible input in %s theme', async theme => { useTheme().setTheme(theme); await open(); expect(document.documentElement.dataset.theme).toBe(theme); expect(wrapper.find('input').attributes('aria-describedby')).toBe('import-rules'); expect(wrapper.text()).toContain('JSON 格式') })
})
