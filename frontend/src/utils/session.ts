export const TOKEN_KEY = 'email_access_token'
const REASON_KEY = 'email_login_reason'
export type LoginReason = 'expired' | 'changed' | 'logout'
export const LOGIN_MESSAGES = {
  expired: '登录状态已失效，请重新登录。',
  changed: '管理员信息已修改，请使用新用户名和密码登录',
  logout: '',
}
let notified = false

export function loginReason(): LoginReason | null {
  const value = sessionStorage.getItem(REASON_KEY)
  return value === 'expired' || value === 'changed' || value === 'logout' ? value : null
}
export function clearSession(reason: LoginReason = 'expired') {
  localStorage.removeItem(TOKEN_KEY)
  sessionStorage.setItem(REASON_KEY, reason)
  if (!notified || reason === 'changed') {
    notified = true
    window.dispatchEvent(new CustomEvent('email-auth-expired', { detail: { reason } }))
  }
}
export function establishSession(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
  sessionStorage.removeItem(REASON_KEY)
  notified = false
}
export function validLocalSession(): boolean {
  const token = localStorage.getItem(TOKEN_KEY)
  if (!token) return false
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    if (typeof payload.exp === 'number' && payload.exp * 1000 > Date.now()) return true
  } catch { /* Malformed sessions are never accepted by the route guard. */ }
  clearSession()
  return false
}
export function isAuthFailure(error: unknown): boolean {
  const response = (error as { response?: { status?: number; data?: { detail?: { code?: string } } } })?.response
  return response?.status === 401 || ['AUTH_SESSION_REVOKED', 'ADMIN_CREDENTIALS_CHANGED'].includes(response?.data?.detail?.code ?? '')
}
export function synchronizeSession(event: StorageEvent) {
  if (event.key === TOKEN_KEY && event.oldValue && !event.newValue) clearSession()
}
