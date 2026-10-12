export interface Mailbox {
  id: number
  email_address: string
  local_part: string
  display_name: string | null
  enabled: boolean
  expires_at: string | null
  created_source: string
  tag_ids: number[]
  email_count: number
  unread_count: number
  latest_email_at: string | null
}

export interface MailboxPage {
  items: Mailbox[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface DashboardStats {
  mailbox_count: number
  email_count: number
  unread_email_count: number
  tag_count: number
}

export interface SystemSetting {
  key: string
  label: string
  value: string
  editable: boolean
  requires_restart: boolean
}

export interface EmailItem {
  id: number
  mailbox_id: number
  sender: string
  receiver: string
  subject: string | null
  body_text: string | null
  body_html: string | null
  verification_code: string | null
  is_read: boolean
  message_date: string | null
  received_at: string
  attachments: Attachment[]
}

export interface Attachment {
  id: number
  original_name: string
  stored_name: string
  mime_type: string | null
  file_size: number
}

export interface Tag {
  id: number
  name: string
}
