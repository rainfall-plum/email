import type { OutboundDraft } from '../types'

export function validateOutbound(draft: OutboundDraft) {
  const errors = { sender_mailbox_id: '', recipient: '', subject: '', body_text: '' }
  if (!draft.sender_mailbox_id) errors.sender_mailbox_id = '请选择发件邮箱'
  if (draft.recipient.length > 254 || !/^[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+$/.test(draft.recipient)) errors.recipient = '请输入单个有效邮箱'
  if (!draft.subject.trim()) errors.subject = '请输入主题'
  else if (draft.subject.length > 200 || /[\r\n\t\x00-\x1f]/.test(draft.subject)) errors.subject = '主题最多200个字符，不能换行或包含控制字符'
  if (!draft.body_text.trim()) errors.body_text = '请输入纯文本正文'
  else if (draft.body_text.length > 100000 || /[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(draft.body_text)) errors.body_text = '正文过长或包含控制字符'
  return errors
}
