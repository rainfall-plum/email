import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import App from '../App.vue'
import { clearSession, establishSession, TOKEN_KEY } from '../utils/session'
const route = vi.hoisted(() => ({ path: '/settings', name: '设置' }))
const replace = vi.hoisted(() => vi.fn())
vi.mock('vue-router', async () => { const { reactive } = await import('vue'); const current = reactive(route); return { useRouter: () => ({ replace }), useRoute: () => current } })
let wrapper: VueWrapper
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); sessionStorage.clear(); establishSession('synthetic'); route.path = '/settings'; replace.mockResolvedValue(undefined); vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({ close: vi.fn() })); wrapper = mount(App, { global: { plugins: [ElementPlus], stubs: { RouterView: true, ThemeSwitcher: true, ElMenu: true } } }) })
afterEach(() => { wrapper.unmount(); vi.restoreAllMocks() })
describe('global session UI', () => {
  it('shows one friendly message and only one redirect for simultaneous failures', async () => {
    clearSession(); clearSession(); clearSession(); await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalledTimes(1); expect(ElMessage.warning).toHaveBeenCalledWith('登录状态已失效，请重新登录。'); expect(replace).toHaveBeenCalledTimes(1); expect(replace).toHaveBeenCalledWith('/login')
  })
  it('redirects after credentials change and preserves the login-page reason', async () => { clearSession('changed'); await flushPromises(); expect(ElMessage.warning).toHaveBeenCalledWith('管理员信息已修改，请使用新用户名和密码登录'); expect(replace).toHaveBeenCalledTimes(1) })
  it('handles logout from another tab and ignores duplicate events on the login page', async () => {
    window.dispatchEvent(new StorageEvent('storage', { key: TOKEN_KEY, oldValue: 'synthetic', newValue: null })); await flushPromises(); expect(replace).toHaveBeenCalledWith('/login'); expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    const { useRoute } = await import('vue-router'); (useRoute() as unknown as { path: string }).path = '/login'; establishSession('synthetic'); clearSession(); await flushPromises(); expect(replace).toHaveBeenCalledTimes(1)
  })
})
