<script setup lang="ts">
import { isAuthFailure } from '../utils/session'
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Collection, CircleCheck, DataAnalysis, Message, MessageBox, Tickets, Warning } from '@element-plus/icons-vue'
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

const readEmails = computed(() => Math.max(totalEmails.value - unreadEmails.value, 0))
const readRate = computed(() => totalEmails.value > 0 ? Math.round((readEmails.value / totalEmails.value) * 100) : 0)
const unreadRate = computed(() => totalEmails.value > 0 ? Math.round((unreadEmails.value / totalEmails.value) * 100) : 0)
const averageEmailsPerMailbox = computed(() => mailboxes.value > 0 ? (totalEmails.value / mailboxes.value).toFixed(1) : '0.0')
const tagsPerMailbox = computed(() => mailboxes.value > 0 ? (tagCount.value / mailboxes.value).toFixed(1) : '0.0')
const processingTone = computed(() => {
  if (totalEmails.value === 0) return 'empty'
  if (unreadRate.value === 0) return 'clear'
  if (unreadRate.value <= 20) return 'steady'
  return 'attention'
})
const processingMessage = computed(() => {
  if (processingTone.value === 'empty') return '还没有收到邮件，邮箱已准备就绪'
  if (processingTone.value === 'clear') return '所有邮件都已处理，收件箱保持清爽'
  if (processingTone.value === 'steady') return `未读邮件占比 ${unreadRate.value}%，处理压力较低`
  return `有 ${unreadEmails.value} 封未读邮件，建议优先查看`
})
const donutStyle = computed(() => ({
  background: `conic-gradient(var(--primary) 0 ${readRate.value}%, color-mix(in srgb, var(--accent) 28%, var(--surface)) ${readRate.value}% 100%)`,
}))

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
  } catch (error) {
    loadError.value = true
    if (!isAuthFailure(error)) ElMessage.error('统计数据加载失败，请重试')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-heading">
    <div><h1>运行概览</h1><p>查看本地邮件接收系统运行概况</p></div>
    <el-button :loading="loading" @click="load">刷新数据</el-button>
  </div>
  <el-result v-if="loadError" icon="error" title="统计数据加载失败" sub-title="请检查网络后重试">
    <template #extra><el-button type="primary" :loading="loading" @click="load">重新加载</el-button></template>
  </el-result>
  <template v-else>
    <el-row class="dashboard-stat-grid" :gutter="18">
      <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card is-action" role="button" tabindex="0" aria-label="查看邮箱管理" @click="router.push('/mailboxes')" @keydown.enter="router.push('/mailboxes')" @keydown.space.prevent="router.push('/mailboxes')"><el-icon class="theme-switcher-icon" :size="24"><MessageBox /></el-icon><div class="stat-value">{{ mailboxes }}</div><div class="stat-label">邮箱总数</div><div class="stat-hint">管理接收地址</div></el-card></el-col>
      <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card is-action" role="button" tabindex="0" aria-label="查看邮箱邮件" @click="router.push('/mailboxes')" @keydown.enter="router.push('/mailboxes')" @keydown.space.prevent="router.push('/mailboxes')"><el-icon class="theme-switcher-icon" :size="24"><Message /></el-icon><div class="stat-value">{{ totalEmails }}</div><div class="stat-label">已接收邮件</div><div class="stat-hint">按邮箱浏览</div></el-card></el-col>
      <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card is-action" role="button" tabindex="0" aria-label="查看未读邮件" @click="router.push('/mailboxes')" @keydown.enter="router.push('/mailboxes')" @keydown.space.prevent="router.push('/mailboxes')"><el-icon class="theme-switcher-icon" :size="24"><Warning /></el-icon><div class="stat-value">{{ unreadEmails }}</div><div class="stat-label">未读邮件</div><div class="stat-hint">优先处理新消息</div></el-card></el-col>
      <el-col :xs="24" :sm="12" :md="6"><el-card class="stat-card is-action" role="button" tabindex="0" aria-label="查看标签管理" @click="router.push('/tags')" @keydown.enter="router.push('/tags')" @keydown.space.prevent="router.push('/tags')"><el-icon class="theme-switcher-icon" :size="24"><CircleCheck /></el-icon><div class="stat-value">{{ tagCount }}</div><div class="stat-label">标签数量</div><div class="stat-hint">整理邮箱</div></el-card></el-col>
    </el-row>

    <section class="dashboard-analytics" aria-labelledby="dashboard-analytics-title">
      <div class="section-heading">
        <div><h2 id="dashboard-analytics-title">收件箱观察</h2><p>用处理状态和邮箱负载快速了解邮件接收情况</p></div>
        <span class="analytics-caption"><DataAnalysis :size="16" aria-hidden="true" />实时汇总</span>
      </div>
      <div class="analytics-grid">
        <el-card class="panel-card analytics-card processing-card">
          <div class="analytics-card-header"><div><strong>邮件处理状态</strong><span>已读与待处理邮件的比例</span></div><span class="status-dot" :class="`is-${processingTone}`" aria-hidden="true"></span></div>
          <div class="processing-chart">
            <div class="donut-chart" :style="donutStyle" role="img" :aria-label="`已读邮件 ${readRate}%，未读邮件 ${unreadRate}%`"><div class="donut-center"><strong>{{ readRate }}<small>%</small></strong><span>已读</span></div></div>
            <div class="chart-legend">
              <div class="legend-row"><span class="legend-key is-read"></span><span>已读邮件</span><strong>{{ readEmails }}</strong></div>
              <div class="legend-row"><span class="legend-key is-unread"></span><span>未读邮件</span><strong>{{ unreadEmails }}</strong></div>
              <div class="legend-total">共 {{ totalEmails }} 封邮件</div>
            </div>
          </div>
          <div class="processing-insight" :class="`is-${processingTone}`"><CircleCheck v-if="processingTone === 'clear'" :size="17" aria-hidden="true" /><Warning v-else-if="processingTone === 'attention'" :size="17" aria-hidden="true" /><Message v-else :size="17" aria-hidden="true" /><span>{{ processingMessage }}</span></div>
        </el-card>

        <el-card class="panel-card analytics-card load-card">
          <div class="analytics-card-header"><div><strong>邮箱负载</strong><span>当前系统中的接收资源</span></div><Collection :size="20" class="analytics-icon" aria-hidden="true" /></div>
          <div class="load-metrics">
            <div class="load-metric"><div class="metric-label"><span>未读压力</span><strong>{{ unreadRate }}%</strong></div><div class="metric-track" role="progressbar" aria-label="未读邮件比例" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="unreadRate"><span class="metric-fill is-warm" :style="{ width: `${unreadRate}%` }"></span></div></div>
            <div class="load-metric"><div class="metric-label"><span>已读完成度</span><strong>{{ readRate }}%</strong></div><div class="metric-track" role="progressbar" aria-label="已读邮件比例" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="readRate"><span class="metric-fill" :style="{ width: `${readRate}%` }"></span></div></div>
            <div class="load-summary"><div><Tickets :size="17" aria-hidden="true" /><span>每个邮箱平均</span><strong>{{ averageEmailsPerMailbox }} 封</strong></div><div><Collection :size="17" aria-hidden="true" /><span>每个邮箱平均标签</span><strong>{{ tagsPerMailbox }} 个</strong></div></div>
          </div>
          <div class="load-footer"><span>邮箱 {{ mailboxes }} 个</span><span>标签 {{ tagCount }} 个</span></div>
        </el-card>
      </div>
    </section>

    <el-card class="panel-card dashboard-status">
      <template #header><strong>系统状态</strong></template>
      <el-descriptions :column="2"><el-descriptions-item label="运行环境">：{{ environment }}</el-descriptions-item><el-descriptions-item label="存储策略">：每邮箱最多 {{ retentionLimit }} 封</el-descriptions-item><el-descriptions-item label="验证码识别">：4~8 位数字</el-descriptions-item><el-descriptions-item label="HTML 展示">：Sandbox iframe</el-descriptions-item></el-descriptions>
    </el-card>
  </template>
</template>

<style scoped>
.dashboard-analytics { margin-top: 28px; }
.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin: 0 2px 14px; }
.section-heading h2 { margin: 0; font-family: Georgia, "Songti SC", SimSun, serif; font-size: 20px; }
.section-heading p { margin: 7px 0 0; color: var(--text-muted); font-size: 13px; }
.analytics-caption { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border: 1px solid var(--border); border-radius: 999px; color: var(--text-muted); font-size: 12px; white-space: nowrap; }
.analytics-grid { display: grid; grid-template-columns: minmax(0, 1.08fr) minmax(0, .92fr); gap: 18px; }
.analytics-card { margin-bottom: 0; min-height: 300px; }
.analytics-card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.analytics-card-header strong { display: block; font-size: 17px; }
.analytics-card-header span { display: block; margin-top: 6px; color: var(--text-muted); font-size: 12px; }
.status-dot { width: 10px; height: 10px; margin-top: 6px; flex: 0 0 auto; border-radius: 50%; background: var(--primary); box-shadow: 0 0 0 5px var(--primary-soft); }
.status-dot.is-attention { background: #c55b52; box-shadow: 0 0 0 5px var(--danger-soft); }
.status-dot.is-empty { background: var(--text-muted); box-shadow: 0 0 0 5px var(--surface-muted); }
.analytics-icon { color: var(--primary); }
.processing-chart { display: flex; align-items: center; gap: clamp(24px, 5vw, 58px); padding: 26px 4px 22px; }
.donut-chart { position: relative; width: 154px; height: 154px; flex: 0 0 auto; border-radius: 50%; }
.donut-chart::after { position: absolute; inset: 13px; content: ""; border-radius: 50%; background: var(--surface); box-shadow: inset 0 0 0 1px var(--border); }
.donut-center { position: absolute; inset: 0; z-index: 1; display: grid; place-content: center; justify-items: center; }
.donut-center strong { font-size: 31px; line-height: 1; letter-spacing: -.04em; }
.donut-center small { margin-left: 2px; font-size: 15px; }
.donut-center span { margin-top: 7px; color: var(--text-muted); font-size: 12px; }
.chart-legend { min-width: 150px; flex: 1; }
.legend-row { display: grid; grid-template-columns: 10px minmax(0, 1fr) auto; align-items: center; gap: 9px; padding: 8px 0; font-size: 13px; }
.legend-row strong { font-size: 15px; }
.legend-key { width: 9px; height: 9px; border-radius: 50%; background: var(--primary); }
.legend-key.is-unread { background: var(--accent); }
.legend-total { margin-top: 13px; color: var(--text-muted); font-size: 12px; }
.processing-insight { display: flex; align-items: center; gap: 9px; padding: 11px 13px; border: 1px solid color-mix(in srgb, var(--primary) 28%, var(--border)); border-radius: 11px; background: var(--primary-soft); color: var(--primary-strong); font-size: 12px; line-height: 1.5; }
.processing-insight.is-attention { border-color: color-mix(in srgb, #c55b52 34%, var(--border)); background: var(--danger-soft); color: #a24943; }
.processing-insight.is-empty { background: var(--surface-soft); color: var(--text-muted); }
.load-metrics { display: grid; gap: 19px; padding: 32px 2px 22px; }
.metric-label { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }
.metric-label strong { color: var(--primary-strong); }
.metric-track { height: 9px; margin-top: 9px; overflow: hidden; border-radius: 999px; background: var(--surface-muted); }
.metric-fill { display: block; height: 100%; border-radius: inherit; background: var(--primary); transition: width .35s ease; }
.metric-fill.is-warm { background: var(--accent); }
.load-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; padding-top: 4px; }
.load-summary > div { display: grid; grid-template-columns: auto 1fr; align-items: center; column-gap: 7px; row-gap: 4px; padding: 11px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface-soft); color: var(--text-muted); font-size: 11px; }
.load-summary svg { grid-row: span 2; color: var(--primary); }
.load-summary strong { color: var(--text); font-size: 14px; }
.load-footer { display: flex; justify-content: space-between; gap: 12px; border-top: 1px solid var(--border); padding-top: 13px; color: var(--text-muted); font-size: 12px; }
@media (max-width: 760px) { .analytics-grid { grid-template-columns: 1fr; } }
@media (max-width: 480px) {
  .section-heading { align-items: flex-start; flex-direction: column; }
  .processing-chart { gap: 18px; padding-inline: 0; }
  .donut-chart { width: 126px; height: 126px; }
  .donut-chart::after { inset: 11px; }
  .donut-center strong { font-size: 26px; }
  .load-summary { grid-template-columns: 1fr; }
}
</style>
