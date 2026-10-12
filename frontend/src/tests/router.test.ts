import { beforeEach, describe, expect, it, vi } from 'vitest'
import { establishSession, TOKEN_KEY } from '../utils/session'
const state = vi.hoisted(() => ({ guard: undefined as ((to: { path: string; meta: { requiresAuth?: boolean } }) => Promise<unknown>) | undefined, profile: vi.fn() }))
vi.mock('vue-router', () => ({ createRouter: () => ({ beforeEach: (guard: typeof state.guard) => { state.guard = guard } }), createWebHistory: vi.fn(), useRouter: vi.fn(), useRoute: vi.fn() }))
vi.mock('../api', () => ({ adminApi: { profile: state.profile } }))
import '../router'
const page = { path: '/settings', meta: { requiresAuth: true } }
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); sessionStorage.clear() })
describe('route protection', () => {
  it('redirects missing and malformed tokens without rendering the protected page', async () => { expect(await state.guard!(page)).toBe('/login'); establishSession('malformed'); expect(await state.guard!(page)).toBe('/login'); expect(state.profile).not.toHaveBeenCalled() })
  it('queries the server to reject revoked sessions before protected navigation', async () => {
    establishSession(`header.${btoa(JSON.stringify({ exp: Date.now() / 1000 + 600 }))}.signature`)
    state.profile.mockRejectedValue({ response: { status: 401, data: { detail: { code: 'AUTH_SESSION_REVOKED' } } } })
    expect(await state.guard!(page)).toBe('/login'); expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })
  it('permits active sessions and cancels network-failed navigation without logging out', async () => {
    establishSession(`header.${btoa(JSON.stringify({ exp: Date.now() / 1000 + 600 }))}.signature`)
    state.profile.mockResolvedValue({ username: 'admin' }); expect(await state.guard!(page)).toBeUndefined()
    state.profile.mockRejectedValue(new Error('network')); expect(await state.guard!(page)).toBe(false); expect(localStorage.getItem(TOKEN_KEY)).not.toBeNull()
  })
})
