import { beforeEach, describe, expect, it, vi } from 'vitest'
import { establishSession, TOKEN_KEY } from '../utils/session'
const handlers = vi.hoisted(() => ({ response: undefined as ((error: unknown) => Promise<never>) | undefined, request: undefined as ((config: { headers: Record<string, string> }) => unknown) | undefined, post: vi.fn(), patch: vi.fn(), get: vi.fn() }))
vi.mock('axios', () => ({ default: { create: () => ({ interceptors: { request: { use: (fn: typeof handlers.request) => { handlers.request = fn } }, response: { use: (_: unknown, fn: typeof handlers.response) => { handlers.response = fn } } }, post: handlers.post, patch: handlers.patch, get: handlers.get }) } }))
import { adminApi, authApi, getApiErrorMessage, mailboxApi } from '../api'
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); sessionStorage.clear(); establishSession('synthetic') })
describe('API authentication and payloads', () => {
  it.each([{ status: 401 }, { status: 403, data: { detail: { code: 'AUTH_SESSION_REVOKED' } } }, { status: 400, data: { detail: { code: 'ADMIN_CREDENTIALS_CHANGED' } } }])('clears session for expired authentication', async response => {
    await expect(handlers.response!({ response, config: { url: '/admin/profile' } })).rejects.toBeDefined(); expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })
  it('does not expire session for incorrect login or temporary network errors', async () => {
    await expect(handlers.response!({ response: { status: 401 }, config: { url: '/login' } })).rejects.toBeDefined(); expect(localStorage.getItem(TOKEN_KEY)).toBe('synthetic')
    await expect(handlers.response!(new Error('network'))).rejects.toBeDefined(); expect(localStorage.getItem(TOKEN_KEY)).toBe('synthetic')
  })
  it('sends a file in multipart form without a client-selected domain', async () => {
    handlers.post.mockResolvedValue({ data: { total: 1 } }); const file = new File(['{}'], 'names.json'); await mailboxApi.importUsernames(file)
    const [path, payload] = handlers.post.mock.calls[0]; expect(path).toBe('/mailboxes/import-usernames'); expect(payload.get('file')).toBe(file); expect(Array.from(payload.keys())).toEqual(['file'])
  })
  it('uses the dedicated account endpoints and never persists passwords', async () => {
    handlers.get.mockResolvedValue({ data: { id: 1, username: 'admin' } }); handlers.patch.mockResolvedValue({ data: { code: 'ADMIN_CREDENTIALS_CHANGED' } })
    await adminApi.profile(); await adminApi.credentials({ current_password: 'synthetic-fixture', new_username: 'renamed' })
    expect(handlers.get).toHaveBeenCalledWith('/admin/profile'); expect(handlers.patch).toHaveBeenCalledWith('/admin/credentials', { current_password: 'synthetic-fixture', new_username: 'renamed' }); expect(JSON.stringify(localStorage)).not.toContain('synthetic-fixture')
  })
  it('maps only approved error codes and clears old login reason on login', async () => {
    expect(getApiErrorMessage({ response: { status: 400, data: { detail: { code: 'CURRENT_PASSWORD_INCORRECT', message: 'internal' } } } }, 'safe')).toBe('当前密码不正确')
    expect(getApiErrorMessage({ response: { status: 500, data: { detail: 'database path' } } }, 'safe')).toBe('safe')
    handlers.post.mockResolvedValue({ data: { access_token: 'new-synthetic' } }); sessionStorage.setItem('email_login_reason', 'expired'); await authApi.login('admin', 'synthetic-fixture'); expect(sessionStorage.getItem('email_login_reason')).toBeNull()
  })
})
