<script setup lang="ts">
import { isAuthFailure } from '../utils/session'
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Message, MessageBox, CircleCheck, Bell } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { dashboardApi, settingsApi } from '../api'

const totalEmails = ref(0)
const mailboxes = ref(0)
const unreadEmails = ref(0)
const tagCount = ref(0)
const loading = ref(true)
const loadError = ref(false)
const environment = ref('加载中')
const retentionLimit = ref('10')
const router = useRouter()

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const [stats, settingData] = await Promise.all([dashboardApi.stats(), settingsApi.list()])
    totalEmails.value = stats.email_count
    unreadEmails.value = stats.unread_email_count
    tagCount.value = stats.tag_count
    const mailboxCount = stats.mailbox_count
    environment.value = settingData.find((item) => item.key === 'environment')?.value || '未知'
    retentionLimit.value = settingData.find((item) => item.key === 'max_emails_per_mailbox')?.value || '10'
    mailboxes.value = mailboxCount
  } catch (error) { loadError.value = true; if (!isAuthFailure(error)) ElMessage.error('统计数据加载失败，请重试') } finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><h1>Dashboard</h1><p>查看本地邮件接收系统运行概况</p></div><el-button :loading="loading" @click="load">刷新数据</el-button></div>
  <el-result v-if="loadError" icon="error" title="统计数据加载失败" sub-title="请检查网络后重试"><template #extra><el-button type="primary" :loading="loading" @click="load">重新加载</el-button></template></el-result>
  <template v-else><el-row class="dashboard-stat-grid" :gutter="18">
    <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card is-action" role="button" tabindex="0" aria-label="查看邮箱管理" @click="router.push('/mailboxes')" @keydown.enter="router.push('/mailboxes')" @keydown.space.prevent="router.push('/mailboxes')"><el-icon class="theme-switcher-icon" :size="24"><MessageBox /></el-icon><div class="stat-value">{{ mailboxes }}</div><div class="stat-label">邮箱总数</div><div class="stat-hint">管理接收地址</div></el-card></el-col>
    <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card is-action" role="button" tabindex="0" aria-label="查看邮箱邮件" @click="router.push('/mailboxes')" @keydown.enter="router.push('/mailboxes')" @keydown.space.prevent="router.push('/mailboxes')"><el-icon class="theme-switcher-icon" :size="24"><Message /></el-icon><div class="stat-value">{{ totalEmails }}</div><div class="stat-label">已接收邮件</div><div class="stat-hint">按邮箱浏览</div></el-card></el-col>
    <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card is-action" role="button" tabindex="0" aria-label="查看未读邮件" @click="router.push('/mailboxes')" @keydown.enter="router.push('/mailboxes')" @keydown.space.prevent="router.push('/mailboxes')"><el-icon class="theme-switcher-icon" :size="24"><Bell /></el-icon><div class="stat-value">{{ unreadEmails }}</div><div class="stat-label">未读邮件</div><div class="stat-hint">优先处理新消息</div></el-card></el-col>
    <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card is-action" role="button" tabindex="0" aria-label="查看标签管理" @click="router.push('/tags')" @keydown.enter="router.push('/tags')" @keydown.space.prevent="router.push('/tags')"><el-icon class="theme-switcher-icon" :size="24"><CircleCheck /></el-icon><div class="stat-value">{{ tagCount }}</div><div class="stat-label">标签数量</div><div class="stat-hint">整理邮箱</div></el-card></el-col>
  </el-row>
  <el-card class="panel-card dashboard-status"><template #header><strong>系统状态</strong></template><el-descriptions :column="2"><el-descriptions-item label="运行环境">：{{ environment }}</el-descriptions-item><el-descriptions-item label="存储策略">：每邮箱最多 {{ retentionLimit }} 封</el-descriptions-item><el-descriptions-item label="验证码识别">：4~8 位数字</el-descriptions-item><el-descriptions-item label="HTML 展示">：Sandbox iframe</el-descriptions-item></el-descriptions></el-card></template>
</template>
