import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearSession, establishSession, isAuthFailure, loginReason, synchronizeSession, TOKEN_KEY, validLocalSession } from '../utils/session'
const token = (exp: number) => `header.${btoa(JSON.stringify({ exp }))}.signature`
beforeEach(() => { localStorage.clear(); sessionStorage.clear(); establishSession(token(Date.now() / 1000 + 60)) })
describe('session lifecycle', () => {
  it('accepts a live token, rejects missing, malformed and expired sessions', () => {
    expect(validLocalSession()).toBe(true)
    localStorage.removeItem(TOKEN_KEY); expect(validLocalSession()).toBe(false)
    establishSession('invalid'); expect(validLocalSession()).toBe(false)
    establishSession(token(0)); expect(validLocalSession()).toBe(false)
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })
  it.each([{ status: 401 }, { status: 403, data: { detail: { code: 'AUTH_SESSION_REVOKED' } } }, { status: 400, data: { detail: { code: 'ADMIN_CREDENTIALS_CHANGED' } } }])('recognizes authentication expiry independently of status', response => {
    expect(isAuthFailure({ response })).toBe(true)
  })
  it('does not classify network failure as invalid credentials', () => { expect(isAuthFailure(new Error('network'))).toBe(false) })
  it('emits only one expiry notification and remembers a safe reason', () => {
    const callback = vi.fn(); window.addEventListener('email-auth-expired', callback)
    clearSession(); clearSession(); clearSession()
    expect(callback).toHaveBeenCalledTimes(1); expect(loginReason()).toBe('expired')
    establishSession(token(Date.now() / 1000 + 60)); expect(loginReason()).toBeNull()
    clearSession('changed'); expect(loginReason()).toBe('changed'); expect(callback).toHaveBeenCalledTimes(2)
    window.removeEventListener('email-auth-expired', callback)
  })
  it('synchronizes another tab removing its token and ignores theme changes', () => {
    synchronizeSession(new StorageEvent('storage', { key: 'email_theme_mode', oldValue: 'dark', newValue: 'paper' }))
    expect(validLocalSession()).toBe(true)
    synchronizeSession(new StorageEvent('storage', { key: TOKEN_KEY, oldValue: 'previous', newValue: null }))
    expect(validLocalSession()).toBe(false); expect(loginReason()).toBe('expired')
  })
})
