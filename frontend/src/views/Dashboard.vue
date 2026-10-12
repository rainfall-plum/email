<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Message, MessageBox, CircleCheck, Warning } from '@element-plus/icons-vue'

import { dashboardApi, settingsApi } from '../api'

const totalEmails = ref(0)
const mailboxes = ref(0)
const unreadEmails = ref(0)
const tagCount = ref(0)
const loading = ref(true)
const environment = ref('加载中')
const retentionLimit = ref('10')

async function load() {
  loading.value = true
  try {
    const [stats, settingData] = await Promise.all([dashboardApi.stats(), settingsApi.list()])
    totalEmails.value = stats.email_count
    unreadEmails.value = stats.unread_email_count
    tagCount.value = stats.tag_count
    const mailboxCount = stats.mailbox_count
    environment.value = settingData.find((item) => item.key === 'environment')?.value || '未知'
    retentionLimit.value = settingData.find((item) => item.key === 'max_emails_per_mailbox')?.value || '10'
    mailboxes.value = mailboxCount
  } catch { ElMessage.error('统计数据加载失败') } finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><h1>Dashboard</h1><p>查看本地邮件接收系统运行概况</p></div><el-button :loading="loading" @click="load">刷新数据</el-button></div>
  <el-row :gutter="18">
    <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card"><el-icon color="#25a992" :size="24"><MessageBox /></el-icon><div class="stat-value">{{ mailboxes }}</div><div class="stat-label">邮箱总数</div></el-card></el-col>
    <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card"><el-icon color="#4b83e8" :size="24"><Message /></el-icon><div class="stat-value">{{ totalEmails }}</div><div class="stat-label">已接收邮件</div></el-card></el-col>
    <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card"><el-icon color="#ef9b42" :size="24"><Warning /></el-icon><div class="stat-value">{{ unreadEmails }}</div><div class="stat-label">未读邮件</div></el-card></el-col>
    <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card"><el-icon color="#7c65d7" :size="24"><CircleCheck /></el-icon><div class="stat-value">{{ tagCount }}</div><div class="stat-label">标签数量</div></el-card></el-col>
  </el-row>
  <el-card class="panel-card dashboard-status"><template #header><strong>系统状态</strong></template><el-descriptions :column="2"><el-descriptions-item label="运行环境">{{ environment }}</el-descriptions-item><el-descriptions-item label="存储策略">每邮箱最多 {{ retentionLimit }} 封</el-descriptions-item><el-descriptions-item label="验证码识别">4–8 位数字</el-descriptions-item><el-descriptions-item label="HTML 展示">Sandbox iframe</el-descriptions-item></el-descriptions></el-card>
</template>
