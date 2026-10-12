<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { outboundApi, getApiErrorMessage } from '../api'
import type { OutboundEmail, OutboundStatus } from '../types'
import { formatDate } from '../utils/email'

const router = useRouter()
const labels: Record<OutboundStatus, string> = { queued: '等待发送', sending: '正在发送', sent: '已交给 Postfix', retrying: '等待重试', failed: '发送失败' }
const rows = ref<OutboundEmail[]>([]); const total = ref(0); const page = ref(1); const pageSize = ref(20)
const status = ref('all'); const sort = ref('created_desc'); const loading = ref(false); const error = ref(false)
const selected = ref<OutboundEmail | null>(null); const dialog = ref(false); const detailLoading = ref(false); const detailError = ref(false)
const detailId = ref<number | null>(null); const retrying = ref<number | null>(null)
let timer: ReturnType<typeof setInterval> | undefined; let generation = 0
async function load() {
  const request = ++generation
  loading.value = true
  try {
    const data = await outboundApi.list({ page: page.value, page_size: pageSize.value, status: status.value === 'all' ? undefined : status.value, sort: sort.value })
    if (request !== generation) return
    rows.value = data.items; total.value = data.total; error.value = false
  } catch { if (request === generation) error.value = true } finally { if (request === generation) loading.value = false }
}
function filter() { page.value = 1; load() }
async function details(id: number) {
  detailId.value = id; dialog.value = true; selected.value = null; detailLoading.value = true; detailError.value = false
  try { selected.value = await outboundApi.get(id) } catch { detailError.value = true } finally { detailLoading.value = false }
}
async function retry(row: OutboundEmail) {
  if (retrying.value !== null) return
  retrying.value = row.id
  try {
    try { await ElMessageBox.confirm('确认重新尝试发送这封失败邮件？尝试总次数不会重置，最多5次。', '重试确认', { confirmButtonText: '确认重试', cancelButtonText: '取消', type: 'warning' }) } catch { return }
    await outboundApi.retry(row.id); ElMessage.success('已加入发送队列'); await load()
    if (dialog.value && detailId.value === row.id) await details(row.id)
  } catch (e) { ElMessage.error(getApiErrorMessage(e, '重试失败，请刷新记录后重试')) } finally { retrying.value = null }
}
onMounted(() => { load(); timer = setInterval(() => { if (!loading.value && !document.hidden && !dialog.value) load() }, 5000) })
onBeforeUnmount(() => { generation++; clearInterval(timer) })
</script>

<template>
  <div class="page-heading"><div><h1>发送记录</h1><p>最多尝试5次，失败后依次间隔1、5、15、30分钟。已交给 Postfix 不代表收件人已收到。</p></div><div class="page-actions"><el-button :loading="loading" @click="load">刷新</el-button><el-button type="primary" @click="router.push('/outbound/new')">发送邮件</el-button></div></div>
  <el-card class="panel-card filter-card" shadow="never"><el-form class="filter-grid" label-position="top"><el-form-item label="发送状态"><el-select v-model="status" @change="filter"><el-option label="全部状态" value="all" /><el-option v-for="(label, key) in labels" :key="key" :label="label" :value="key" /></el-select></el-form-item><el-form-item label="创建时间排序"><el-select v-model="sort" @change="filter"><el-option label="最新创建优先" value="created_desc" /><el-option label="最早创建优先" value="created_asc" /></el-select></el-form-item></el-form></el-card>
  <el-card class="panel-card" shadow="never">
    <el-result v-if="error" icon="error" title="发送记录加载失败"><template #extra><el-button @click="load">重新加载</el-button></template></el-result>
    <el-table v-else v-loading="loading" :data="rows" empty-text="暂无发送记录">
      <el-table-column prop="sender" label="发件人" min-width="210" show-overflow-tooltip />
      <el-table-column prop="recipient" label="收件人" min-width="210" show-overflow-tooltip />
      <el-table-column prop="subject" label="主题" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="150"><template #default="{ row }"><el-tag :type="row.status === 'failed' ? 'danger' : row.status === 'sent' ? 'success' : 'info'">{{ labels[row.status as OutboundStatus] }}</el-tag></template></el-table-column>
      <el-table-column label="尝试次数" width="100"><template #default="{ row }">{{ row.attempt_count }}/{{ row.max_attempts }}</template></el-table-column>
      <el-table-column label="创建时间" min-width="185"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
      <el-table-column label="下次重试" min-width="185"><template #default="{ row }">{{ formatDate(row.next_attempt_at) }}</template></el-table-column>
      <el-table-column prop="last_error" label="失败原因" min-width="220" show-overflow-tooltip />
      <el-table-column label="操作" width="155" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="details(row.id)">详情</el-button><el-button v-if="row.status === 'failed'" link type="warning" :loading="retrying === row.id" :disabled="retrying !== null || row.attempt_count >= row.max_attempts" :title="row.attempt_count >= row.max_attempts ? '已达到5次上限' : '重新尝试发送'" @click="retry(row)">重试</el-button></template></el-table-column>
    </el-table>
    <div class="table-footer"><span class="muted">共 {{ total }} 封 · 每5秒自动刷新</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="sizes, prev, pager, next" @current-change="load" @size-change="filter" /></div>
  </el-card>
  <el-dialog v-model="dialog" title="发送详情" width="min(760px, 94vw)">
    <div v-loading="detailLoading">
      <el-result v-if="detailError" icon="error" title="详情加载失败"><template #extra><el-button @click="details(detailId!)">重新加载</el-button></template></el-result>
      <template v-else-if="selected"><dl class="outbound-details"><dt>发件人</dt><dd>{{ selected.sender }}</dd><dt>收件人</dt><dd>{{ selected.recipient }}</dd><dt>主题</dt><dd>{{ selected.subject }}</dd><dt>状态</dt><dd>{{ labels[selected.status] }} · {{ selected.attempt_count }}/{{ selected.max_attempts }} 次</dd><dt>失败原因</dt><dd>{{ selected.last_error || '无' }}</dd><dt>下次重试</dt><dd>{{ formatDate(selected.next_attempt_at) }}</dd><dt>Message-ID</dt><dd>{{ selected.message_id }}</dd><dt>创建时间</dt><dd>{{ formatDate(selected.created_at) }}</dd><dt>发送时间</dt><dd>{{ formatDate(selected.sent_at) }}</dd><dt>失败时间</dt><dd>{{ formatDate(selected.failed_at) }}</dd></dl><h3>纯文本正文</h3><div class="detail-content">{{ selected.body_text }}</div></template>
    </div>
    <template #footer><el-button :disabled="detailLoading" @click="details(detailId!)">刷新详情</el-button><el-button @click="dialog = false">关闭</el-button></template>
  </el-dialog>
</template>
