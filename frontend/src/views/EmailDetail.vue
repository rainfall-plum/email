<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { emailApi } from '../api'
import type { EmailItem } from '../types'
import { sanitizeHtmlForPreview } from '../utils/email'

const route = useRoute(); const router = useRouter(); const email = ref<EmailItem | null>(null); const loading = ref(false)
const downloadingId = ref<number | null>(null)
const safeHtml = computed(() => {
  if (!email.value?.body_html) return ''
  return sanitizeHtmlForPreview(email.value.body_html)
})
async function load() { loading.value = true; try { email.value = await emailApi.get(Number(route.params.id)) } catch { ElMessage.error('邮件详情加载失败') } finally { loading.value = false } }
function formatSize(size: number) { return size < 1024 ? `${size} B` : `${(size / 1024).toFixed(1)} KB` }
async function downloadAttachment(id: number, filename: string) {
  downloadingId.value = id
  try {
    const blob = await emailApi.downloadAttachment(id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url)
  } catch { ElMessage.error('附件下载失败') } finally { downloadingId.value = null }
}
onMounted(load)
</script>

<template>
  <div v-loading="loading"><div class="page-heading"><div><el-button link @click="router.back()">← 返回</el-button><h1 style="margin-top: 12px">邮件详情</h1></div></div><el-card v-if="email" class="panel-card"><el-descriptions :column="2" border><el-descriptions-item label="发件人">{{ email.sender }}</el-descriptions-item><el-descriptions-item label="收件人">{{ email.receiver }}</el-descriptions-item><el-descriptions-item label="主题">{{ email.subject || '无主题' }}</el-descriptions-item><el-descriptions-item label="验证码"><span v-if="email.verification_code" class="code-chip">{{ email.verification_code }}</span><span v-else class="muted">未识别</span></el-descriptions-item><el-descriptions-item label="接收时间">{{ email.received_at }}</el-descriptions-item></el-descriptions><el-divider /><h3>正文</h3><div v-if="email.body_text" class="detail-content">{{ email.body_text }}</div><p v-else class="muted">无纯文本正文</p><template v-if="safeHtml"><h3>HTML 正文</h3><iframe class="html-preview" sandbox="" :srcdoc="safeHtml" title="邮件 HTML 内容" referrerpolicy="no-referrer" /></template><template v-if="email.attachments.length"><h3>附件</h3><el-table :data="email.attachments"><el-table-column prop="original_name" label="文件名" /><el-table-column prop="mime_type" label="类型" /><el-table-column label="大小"><template #default="{ row }">{{ formatSize(row.file_size) }}</template></el-table-column><el-table-column label="操作"><template #default="{ row }"><el-button link type="primary" :loading="downloadingId === row.id" @click="downloadAttachment(row.id, row.original_name)">下载</el-button></template></el-table-column></el-table></template></el-card></div>
</template>
