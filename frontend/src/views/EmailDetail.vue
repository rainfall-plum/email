<script setup lang="ts">
import { isAuthFailure } from '../utils/session'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { emailApi, getApiErrorMessage } from '../api'
import type { EmailItem } from '../types'
import { formatDate, sanitizeHtmlForPreview } from '../utils/email'

const route = useRoute(); const router = useRouter(); const email = ref<EmailItem | null>(null); const loading = ref(false)
const downloadingIds = ref<Set<number>>(new Set())
const loadError = ref(false)
let loadSequence = 0
const safeHtml = computed(() => {
  if (!email.value?.body_html) return ''
  return sanitizeHtmlForPreview(email.value.body_html)
})
async function load() { const sequence = ++loadSequence; loading.value = true; loadError.value = false; try { const next = await emailApi.get(Number(route.params.id)); if (sequence === loadSequence) email.value = next } catch (error) { if (sequence === loadSequence) { email.value = null; loadError.value = true; if (!isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '邮件详情加载失败')) } } finally { if (sequence === loadSequence) loading.value = false } }
function formatSize(size: number) { return size < 1024 ? `${size} B` : `${(size / 1024).toFixed(1)} KB` }
async function downloadAttachment(id: number, filename: string) {
  if (downloadingIds.value.has(id)) return
  downloadingIds.value = new Set(downloadingIds.value).add(id)
  try {
    const blob = await emailApi.downloadAttachment(id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url)
  } catch (error) { if (!isAuthFailure(error)) ElMessage.error('附件下载失败') } finally { const next = new Set(downloadingIds.value); next.delete(id); downloadingIds.value = next }
}
function goBack() { router.push(email.value ? `/mailboxes/${email.value.mailbox_id}` : '/mailboxes') }
watch(() => route.params.id, load)
onMounted(load)
</script>

<template>
  <div v-loading="loading"><div class="page-heading"><div><el-button link @click="goBack">返回邮箱</el-button><h1 class="detail-title">邮件详情</h1></div></div><el-result v-if="loadError" icon="error" title="邮件详情暂时无法加载" sub-title="请检查网络后重试"><template #extra><el-button type="primary" :loading="loading" @click="load">重新加载</el-button><el-button @click="goBack">返回邮箱</el-button></template></el-result><el-card v-else-if="email" class="panel-card"><el-descriptions :column="2" :border="true" class="email-meta"><el-descriptions-item label="发件人">{{ email.sender }}</el-descriptions-item><el-descriptions-item label="收件人">{{ email.receiver }}</el-descriptions-item><el-descriptions-item label="主题">{{ email.subject || '无主题' }}</el-descriptions-item><el-descriptions-item label="验证码"><span v-if="email.verification_code" class="code-chip">{{ email.verification_code }}</span><span v-else class="muted">未识别</span></el-descriptions-item><el-descriptions-item label="接收时间">{{ formatDate(email.received_at) }}</el-descriptions-item></el-descriptions><el-divider /><h3>纯文本正文</h3><div v-if="email.body_text" class="detail-content">{{ email.body_text }}</div><p v-else class="muted">这封邮件没有可显示的纯文本正文。</p><template v-if="safeHtml"><h3>HTML 正文</h3><iframe class="html-preview" sandbox="" :srcdoc="safeHtml" title="邮件 HTML 内容" referrerpolicy="no-referrer" /></template><template v-if="email.attachments.length"><h3>附件</h3><el-table :data="email.attachments"><el-table-column prop="original_name" label="文件名" /><el-table-column prop="mime_type" label="类型" /><el-table-column label="大小"><template #default="{ row }">{{ formatSize(row.file_size) }}</template></el-table-column><el-table-column label="操作"><template #default="{ row }"><el-button link type="primary" :loading="downloadingIds.has(row.id)" :disabled="downloadingIds.size > 0 && !downloadingIds.has(row.id)" @click="downloadAttachment(row.id, row.original_name)">下载</el-button></template></el-table-column></el-table></template></el-card></div>
</template>
