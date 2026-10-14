import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import AdminAccount from '../components/AdminAccount.vue'
import Login from '../views/Login.vue'
import { adminApi, authApi } from '../api'
const push = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({ useRouter: () => ({ push, replace: vi.fn() }) }))
vi.mock('../api', () => ({ adminApi: { profile: vi.fn(), credentials: vi.fn(), verifyPassword: vi.fn() }, authApi: { login: vi.fn() }, getApiErrorMessage: (_: unknown, fallback: string) => fallback }))
let wrapper: VueWrapper
async function account() { wrapper = mount(AdminAccount, { global: { plugins: [ElementPlus] }, attachTo: document.body }); await flushPromises() }
function button(text: string) { return wrapper.findAll('button').find(item => item.text().includes(text))! }
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); sessionStorage.clear(); vi.mocked(adminApi.profile).mockResolvedValue({ id: 1, username: 'admin' }); vi.mocked(adminApi.verifyPassword).mockResolvedValue({ valid: true }); vi.mocked(adminApi.credentials).mockResolvedValue({ code: 'ADMIN_CREDENTIALS_CHANGED' }); vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({ close: vi.fn() })); vi.spyOn(ElMessage, 'error').mockImplementation(() => ({ close: vi.fn() })); vi.spyOn(ElMessage, 'success').mockImplementation(() => ({ close: vi.fn() })) })
afterEach(() => { wrapper?.unmount(); document.body.innerHTML = ''; vi.restoreAllMocks() })
describe('administrator account', () => {
  it('shows only the current administrator on the settings page', async () => { await account(); expect(wrapper.text()).toContain('admin'); expect(wrapper.text()).not.toContain('当前管理员用户名'); expect(wrapper.findAll('input')).toHaveLength(0); await button('修改管理员信息').trigger('click'); await flushPromises(); expect(wrapper.text()).toContain('验证当前密码') })
  it('keeps password fields out of the initial page', async () => { await account(); expect(wrapper.findAll('input[type="password"]')).toHaveLength(0); expect(wrapper.text()).toContain('修改管理员信息') })
})
describe('login form', () => {
  it('does not render the old inline expiry alert and prevents repeat submit', async () => { sessionStorage.setItem('email_login_reason', 'changed'); let resolve!: (value: { access_token: string }) => void; vi.mocked(authApi.login).mockImplementation(() => new Promise(done => { resolve = done })); wrapper = mount(Login, { global: { plugins: [ElementPlus] } }); await flushPromises(); expect(wrapper.text()).not.toContain('管理员信息已修改，请使用新用户名和密码登录'); await wrapper.find('input[autocomplete="username"]').setValue('admin'); await wrapper.find('input[autocomplete="current-password"]').setValue('fixture-only'); await wrapper.find('form').trigger('submit'); await wrapper.find('form').trigger('submit'); expect(authApi.login).toHaveBeenCalledTimes(1); resolve({ access_token: 'synthetic' }); await flushPromises(); expect(push).toHaveBeenCalledWith('/dashboard'); expect((wrapper.find('input[autocomplete="current-password"]').element as HTMLInputElement).value).toBe('') })
})
