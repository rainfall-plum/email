import axios from 'axios'
import { clearSession, establishSession, isAuthFailure } from './utils/session'
import type { OutboundDraft, OutboundEmail } from './types'

import type { Attachment, DashboardStats, EmailItem, Mailbox, MailboxPage, SystemSetting, Tag } from './types'

export function isRequestCanceled(error: unknown): boolean {
  return Boolean(
    (error as { code?: string; name?: string })?.code === 'ERR_CANCELED'
      || (error as { name?: string })?.name === 'CanceledError'
      || (error as { name?: string })?.name === 'AbortError',
  )
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('email_access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const sentAuthorization = error.config?.headers?.Authorization
    const currentToken = localStorage.getItem('email_access_token')
    if (error.config?.url !== '/login' && isAuthFailure(error) && (!sentAuthorization || !currentToken || sentAuthorization === `Bearer ${currentToken}`)) clearSession()
    return Promise.reject(error)
  },
)

const SAFE_BUSINESS_ERRORS = new Set([
  '邮箱前缀已存在', '邮箱前缀只允许小写字母和数字', '存在无效标签', '标签名称不能为空',
  '标签名称已存在', '邮箱不存在', '邮件不存在', '附件不存在', '附件文件不存在',
  '不支持的邮箱排序方式', '不支持的标签匹配方式',
  '发件邮箱不存在或不属于系统域名', '提交标识已使用，请刷新后重新创建',
  '仅可重试未满5次的失败邮件', '发送记录不存在',
])
const SAFE_CODES: Record<string, string> = {
  INVALID_CREDENTIALS: '用户名或密码错误', AUTH_UNAVAILABLE: '登录服务暂不可用，请稍后重试',
  CURRENT_PASSWORD_INCORRECT: '当前密码不正确', NO_CREDENTIAL_CHANGES: '请至少修改一项管理员信息',
  CURRENT_PASSWORD_INVALID: '当前密码不正确', INVALID_CURRENT_PASSWORD: '当前密码不正确',
  ADMIN_USERNAME_EXISTS: '管理员用户名已存在', USERNAME_ALREADY_EXISTS: '管理员用户名已存在',
  INVALID_USERNAME: '用户名须为 3–64 位，以字母开头，仅含字母、数字和下划线',
  INVALID_PASSWORD: '新密码须为 4–128 个字符', NO_CHANGES: '请至少修改一项管理员信息',
  invalid_json: 'JSON 解析失败，请检查文件格式和 UTF-8 编码', unsupported_structure: 'JSON 必须是仅包含 usernames 数组的对象',
  file_too_large: '文件不能超过 1 MiB', too_many_usernames: '最多允许 1000 个用户名',
  invalid_extension: '请选择 .json 文件',
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  const response = (error as { response?: { status?: number; data?: { detail?: unknown } } })?.response
  const detail = response?.data?.detail
  if (detail && typeof detail === 'object' && 'code' in detail && typeof detail.code === 'string' && SAFE_CODES[detail.code]) return SAFE_CODES[detail.code]
  if (response?.status && response.status < 500 && typeof detail === 'string' && SAFE_BUSINESS_ERRORS.has(detail)) {
    return detail
  }
  return fallback
}

export const authApi = {
  async login(username: string, password: string) {
    const response = await api.post<{ access_token: string }>('/login', { username, password })
    establishSession(response.data.access_token)
    return response.data
  },
  async me() {
    return (await api.get<{ id: number; username: string }>('/me')).data
  },
  logout() {
    clearSession('logout')
  },
}

export const adminApi = {
  async profile() { return (await api.get<{ id: number; username: string }>('/admin/profile')).data },
  async verifyPassword(current_password: string) { return (await api.post<{ valid: boolean }>('/admin/verify-password', { current_password })).data },
  async credentials(payload: { current_password: string; new_username?: string; new_password?: string; confirm_new_password?: string }) {
    return (await api.patch<{ code: string }>('/admin/credentials', payload)).data
  },
}
export interface ImportResult {
  total: number; success_count: number; duplicate_count: number; invalid_count: number; existing_count: number
  already_available_count?: number; already_used_count?: number
  created_mailboxes: Array<{ username: string; email: string; mailbox_id: number }>
  rejected_usernames: Array<{ username: unknown; reason: string; message: string }>
}

export const mailboxApi = {
  async importUsernames(file: File) {
    const body = new FormData(); body.append('file', file)
    return (await api.post<ImportResult>('/mailboxes/import-usernames', body, { timeout: 60000 })).data
  },
  async list(params: {
    page?: number; page_size?: number; search?: string; tag_ids?: number[]; tag_mode?: 'any' | 'all';
    untagged?: boolean; sort_by?: string
  } = {}, signal?: AbortSignal) {
    const query = new URLSearchParams()
    if (params.page) query.set('page', String(params.page))
    if (params.page_size) query.set('page_size', String(params.page_size))
    if (params.search?.trim()) query.set('search', params.search.trim())
    params.tag_ids?.forEach((id) => query.append('tag_ids', String(id)))
    if (params.tag_mode) query.set('tag_mode', params.tag_mode)
    if (params.untagged) query.set('untagged', 'true')
    if (params.sort_by) query.set('sort_by', params.sort_by)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return (await api.get<MailboxPage>(`/mailboxes${suffix}`, signal ? { signal } : undefined)).data
  },
  async get(id: number, signal?: AbortSignal) { return (await api.get<Mailbox>(`/mailboxes/${id}`, signal ? { signal } : undefined)).data },
  async create(payload: { local_part: string; display_name?: string; tag_ids?: number[] }) {
    return (await api.post<Mailbox>('/mailboxes', payload)).data
  },
  async batch(count: number, tag_ids: number[] = []) {
    return (await api.post<{ mailboxes: Mailbox[] }>('/mailboxes/batch', { count, tag_ids })).data
  },
  async update(id: number, payload: Partial<Mailbox>) { return (await api.put<Mailbox>(`/mailboxes/${id}`, payload)).data },
  async remove(id: number) { await api.delete(`/mailboxes/${id}`) },
  async emails(id: number, signal?: AbortSignal) { return (await api.get<EmailItem[]>(`/mailboxes/${id}/emails`, signal ? { signal } : undefined)).data },
}

export const emailApi = {
  async get(id: number, signal?: AbortSignal) { return (await api.get<EmailItem>(`/emails/${id}`, signal ? { signal } : undefined)).data },
  async downloadAttachment(id: number) {
    return (await api.get<Blob>(`/attachments/${id}/download`, { responseType: 'blob' })).data
  },
}

export const dashboardApi = {
  async stats() { return (await api.get<DashboardStats>('/dashboard/stats')).data },
}

export const tagApi = {
  async list(signal?: AbortSignal) { return (await api.get<Tag[]>('/tags', signal ? { signal } : undefined)).data },
  async create(name: string) { return (await api.post<Tag>('/tags', { name })).data },
  async update(id: number, name: string) { return (await api.put<Tag>(`/tags/${id}`, { name })).data },
  async remove(id: number) { await api.delete(`/tags/${id}`) },
}

export const settingsApi = {
  async list() { return (await api.get<SystemSetting[]>('/settings')).data },
  async update(key: string, value: string) {
    return (await api.put<SystemSetting>(`/settings/${encodeURIComponent(key)}`, { value })).data
  },
}

export type { Attachment }

export const outboundApi = {
  async options(signal?: AbortSignal) { return (await api.get<{ id: number; email_address: string }[]>('/outbound-emails/options', signal ? { signal } : undefined)).data },
  async create(payload: OutboundDraft) { return (await api.post<OutboundEmail>('/outbound-emails', payload)).data },
  async list(params: { page: number; page_size: number; status?: string; sort: string }, signal?: AbortSignal) {
    return (await api.get<{ items: OutboundEmail[]; total: number }>('/outbound-emails', { params, ...(signal ? { signal } : {}) })).data
  },
  async get(id: number, signal?: AbortSignal) { return (await api.get<OutboundEmail>(`/outbound-emails/${id}`, signal ? { signal } : undefined)).data },
  async retry(id: number) { return (await api.post<OutboundEmail>(`/outbound-emails/${id}/retry`)).data },
}
