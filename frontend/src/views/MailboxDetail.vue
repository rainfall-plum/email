<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { mailboxApi } from '../api'
import type { EmailItem } from '../types'

const route = useRoute(); const router = useRouter()
const emails = ref<EmailItem[]>([]); const loading = ref(false)
async function load() { loading.value = true; try { emails.value = await mailboxApi.emails(Number(route.params.id)) } catch { ElMessage.error('邮件加载失败') } finally { loading.value = false } }
function openEmail(row: EmailItem) { router.push(`/emails/${row.id}`) }
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><el-button link @click="router.push('/mailboxes')">← 返回邮箱</el-button><h1 style="margin-top: 12px">邮件列表</h1><p>邮箱 ID：{{ route.params.id }} · 共 {{ emails.length }} 封邮件</p></div><el-button @click="load">刷新</el-button></div>
  <el-card class="panel-card"><el-table v-loading="loading" :data="emails" stripe @row-click="openEmail"><el-table-column label="状态" width="85"><template #default="{ row }"><el-tag :type="row.is_read ? 'info' : 'warning'">{{ row.is_read ? '已读' : '未读' }}</el-tag></template></el-table-column><el-table-column prop="sender" label="发件人" min-width="220" /><el-table-column prop="subject" label="主题" min-width="260" /><el-table-column label="验证码" width="130"><template #default="{ row }"><span v-if="row.verification_code" class="code-chip">{{ row.verification_code }}</span><span v-else class="muted">—</span></template></el-table-column><el-table-column prop="received_at" label="接收时间" min-width="190" /></el-table></el-card>
</template>
