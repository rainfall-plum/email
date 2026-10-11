import axios from 'axios'

import type { Attachment, EmailItem, Mailbox, MailboxPage, SystemSetting, Tag } from './types'

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
    if (error.response?.status === 401) localStorage.removeItem('email_access_token')
    return Promise.reject(error)
  },
)

export const authApi = {
  async login(username: string, password: string) {
    const response = await api.post<{ access_token: string }>('/login', { username, password })
    localStorage.setItem('email_access_token', response.data.access_token)
    return response.data
  },
  async me() {
    return (await api.get<{ id: number; username: string }>('/me')).data
  },
  logout() {
    localStorage.removeItem('email_access_token')
  },
}

export const mailboxApi = {
  async list(params: {
    page?: number; page_size?: number; tag_ids?: number[]; tag_mode?: 'any' | 'all';
    untagged?: boolean; sort_by?: string
  } = {}) {
    const query = new URLSearchParams()
    if (params.page) query.set('page', String(params.page))
    if (params.page_size) query.set('page_size', String(params.page_size))
    params.tag_ids?.forEach((id) => query.append('tag_ids', String(id)))
    if (params.tag_mode) query.set('tag_mode', params.tag_mode)
    if (params.untagged) query.set('untagged', 'true')
    if (params.sort_by) query.set('sort_by', params.sort_by)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return (await api.get<MailboxPage>(`/mailboxes${suffix}`)).data
  },
  async get(id: number) { return (await api.get<Mailbox>(`/mailboxes/${id}`)).data },
  async create(payload: { local_part: string; display_name?: string; tag_ids?: number[] }) {
    return (await api.post<Mailbox>('/mailboxes', payload)).data
  },
  async batch(count: number, tag_ids: number[] = []) {
    return (await api.post<{ mailboxes: Mailbox[] }>('/mailboxes/batch', { count, tag_ids })).data
  },
  async update(id: number, payload: Partial<Mailbox>) { return (await api.put<Mailbox>(`/mailboxes/${id}`, payload)).data },
  async remove(id: number) { await api.delete(`/mailboxes/${id}`) },
  async emails(id: number) { return (await api.get<EmailItem[]>(`/mailboxes/${id}/emails`)).data },
}

export const emailApi = {
  async get(id: number) { return (await api.get<EmailItem>(`/emails/${id}`)).data },
  async downloadAttachment(id: number) {
    return (await api.get<Blob>(`/attachments/${id}/download`, { responseType: 'blob' })).data
  },
}

export const tagApi = {
  async list() { return (await api.get<Tag[]>('/tags')).data },
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
