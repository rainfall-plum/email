import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import AdminAccount from '../components/AdminAccount.vue'
import Login from '../views/Login.vue'
import { adminApi, authApi } from '../api'
import { establishSession, loginReason, TOKEN_KEY } from '../utils/session'
const replace = vi.hoisted(() => vi.fn())
const push = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({ useRouter: () => ({ replace, push }) }))
vi.mock('../api', () => ({ adminApi: { profile: vi.fn(), credentials: vi.fn() }, authApi: { login: vi.fn() }, getApiErrorMessage: (_: unknown, fallback: string) => fallback }))
let wrapper: VueWrapper
function button(text: string) { return wrapper.findAll('button').find(item => item.text().includes(text))! }
async function account() { wrapper = mount(AdminAccount, { global: { plugins: [ElementPlus] }, attachTo: document.body }); await flushPromises() }
async function form(username = 'newadmin') { await wrapper.findAll('input')[0].setValue(username); await wrapper.findAll('input')[1].setValue('current-fixture-only') }
async function password(newPassword = 'new-fixture-only-password', confirmation = newPassword) { await wrapper.find('input[type="checkbox"]').setValue(true); const inputs = wrapper.findAll('input').filter(item => item.attributes('type') !== 'checkbox'); await inputs[2].setValue(newPassword); await inputs[3].setValue(confirmation) }
async function submit() { await wrapper.find('form').trigger('submit'); await flushPromises() }
beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear(); sessionStorage.clear()
  vi.mocked(adminApi.profile).mockResolvedValue({ id: 1, username: 'admin' })
  vi.mocked(adminApi.credentials).mockResolvedValue({ code: 'ADMIN_CREDENTIALS_CHANGED' })
  vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({ close: vi.fn() })); vi.spyOn(ElMessage, 'error').mockImplementation(() => ({ close: vi.fn() })); vi.spyOn(ElMessage, 'success').mockImplementation(() => ({ close: vi.fn() }))
})
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; vi.restoreAllMocks() })
describe('administrator account', () => {
  it('loads current profile with password changes hidden and clears cancelled fields', async () => {
    await account(); expect(wrapper.text()).toContain('admin'); expect(wrapper.findAll('input[type="password"]')).toHaveLength(1)
    await form(); await password(); await button('取消').trigger('click'); expect(wrapper.findAll('input')[0].element.value).toBe('admin'); expect(wrapper.findAll('input')[1].element.value).toBe(''); expect(wrapper.findAll('input[type="password"]')).toHaveLength(1)
  })
  it('requires current password, valid username and actual changes', async () => {
    await account(); await submit(); expect(adminApi.credentials).not.toHaveBeenCalled()
    await form('bad.name'); await submit(); expect(adminApi.credentials).not.toHaveBeenCalled()
    await form('admin'); await submit(); expect(ElMessage.warning).toHaveBeenCalled(); expect(adminApi.credentials).not.toHaveBeenCalled()
  })
  it('validates password length and confirmation', async () => {
    await account(); await form(); await password('abc'); await submit(); expect(adminApi.credentials).not.toHaveBeenCalled()
    await password('new-fixture-only-password', 'different-fixture'); await submit(); expect(adminApi.credentials).not.toHaveBeenCalled()
  })
  it('accepts the configured four-character minimum', async () => {
    await account(); await form('admin'); await password('abcd'); await submit()
    expect(adminApi.credentials).toHaveBeenCalledWith(expect.objectContaining({ new_password: 'abcd', confirm_new_password: 'abcd' }))
  })
  it.each(['username', 'password', 'both'])('supports changing %s and logs out on success', async mode => {
    establishSession('synthetic-session')
    await account(); await form(mode === 'password' ? 'admin' : 'newadmin'); if (mode !== 'username') await password()
    await submit()
    const payload = vi.mocked(adminApi.credentials).mock.calls[0][0]
    expect(payload.current_password).toBe('current-fixture-only'); expect(payload.new_username).toBe(mode === 'password' ? undefined : 'newadmin'); expect(Boolean(payload.new_password)).toBe(mode !== 'username')
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull(); expect(loginReason()).toBe('changed'); expect(replace).not.toHaveBeenCalled()
    expect(wrapper.findAll('input[type="password"]').every(item => (item.element as HTMLInputElement).value === '')).toBe(true)
    expect(Object.values(localStorage)).not.toContain('current-fixture-only')
  })
  it('supports password visibility', async () => {
    await account(); await form(); await wrapper.find('.el-input__password').trigger('click'); expect(wrapper.findAll('input')[1].attributes('type')).toBe('text'); await wrapper.find('.el-input__password').trigger('click'); expect(wrapper.findAll('input')[1].attributes('type')).toBe('password')
  })
  it('prevents duplicate save while displaying loading', async () => {
    let resolve!: (value: { code: string }) => void
    vi.mocked(adminApi.credentials).mockImplementation(() => new Promise(done => { resolve = done }))
    await account(); await form(); await wrapper.find('form').trigger('submit'); await wrapper.find('form').trigger('submit')
    expect(adminApi.credentials).toHaveBeenCalledTimes(1); expect(button('保存管理员信息').classes()).toContain('is-loading'); resolve({ code: 'ADMIN_CREDENTIALS_CHANGED' }); await flushPromises()
  })
  it('shows safe failure, preserves session and removes passwords from fields', async () => {
    establishSession('synthetic-session'); vi.mocked(adminApi.credentials).mockRejectedValue(new Error('internal-database-path'))
    await account(); await form(); await submit(); expect(ElMessage.error).toHaveBeenCalled(); expect(replace).not.toHaveBeenCalled(); expect(localStorage.getItem(TOKEN_KEY)).toBe('synthetic-session'); expect(wrapper.text()).not.toContain('internal-database-path'); expect(wrapper.findAll('input')[1].element.value).toBe('')
  })
})
describe('login form', () => {
  it('shows credential-change reason, prevents repeat submit and clears password', async () => {
    sessionStorage.setItem('email_login_reason', 'changed')
    let resolve!: (value: { access_token: string }) => void
    vi.mocked(authApi.login).mockImplementation(() => new Promise(done => { resolve = done }))
    wrapper = mount(Login, { global: { plugins: [ElementPlus] } }); await flushPromises()
    expect(wrapper.text()).toContain('管理员信息已修改，请使用新用户名和密码登录')
    await wrapper.find('input[autocomplete="username"]').setValue('admin'); await wrapper.find('input[autocomplete="current-password"]').setValue('fixture-only')
    await wrapper.find('form').trigger('submit'); await wrapper.find('form').trigger('submit'); expect(authApi.login).toHaveBeenCalledTimes(1)
    resolve({ access_token: 'synthetic' }); await flushPromises(); expect(push).toHaveBeenCalledWith('/dashboard'); expect((wrapper.find('input[autocomplete="current-password"]').element as HTMLInputElement).value).toBe('')
  })
})
