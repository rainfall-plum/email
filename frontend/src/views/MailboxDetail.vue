<script setup lang="ts">
import { isAuthFailure } from '../utils/session'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { getApiErrorMessage, mailboxApi, tagApi } from '../api'
import type { EmailItem, Mailbox, Tag } from '../types'
import { formatDate } from '../utils/email'

const route = useRoute(); const router = useRouter()
const emails = ref<EmailItem[]>([]); const loading = ref(false)
const mailbox = ref<Mailbox | null>(null)
const tags = ref<Tag[]>([])
const selectedTagIds = ref<number[]>([])
const savingTags = ref(false)
const loadError = ref(false)
const mailboxId = computed(() => Number(route.params.id))
async function load() {
  loading.value = true
  loadError.value = false
  try {
    const [mailboxData, emailData, tagData] = await Promise.all([
      mailboxApi.get(mailboxId.value), mailboxApi.emails(mailboxId.value), tagApi.list(),
    ])
    mailbox.value = mailboxData
    selectedTagIds.value = [...mailboxData.tag_ids]
    emails.value = emailData
    tags.value = tagData
  } catch (error) { loadError.value = true; if (!isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '邮箱数据加载失败')) } finally { loading.value = false }
}
async function saveTags() {
  if (!mailbox.value || savingTags.value) return
  savingTags.value = true
  try {
    mailbox.value = await mailboxApi.update(mailbox.value.id, { tag_ids: selectedTagIds.value })
    ElMessage.success('标签已保存')
  } catch (error) {
    if (!isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '标签保存失败'))
  } finally { savingTags.value = false }
}
function openEmail(row: EmailItem) { router.push(`/emails/${row.id}`) }
async function copyMailboxInfo(event: MouseEvent) {
  event.stopPropagation()
  if (!mailbox.value) return
  try { await navigator.clipboard.writeText(mailbox.value.email_address); ElMessage.success('邮箱地址已复制') }
  catch (error) { if (!isAuthFailure(error)) ElMessage.error('复制失败，请检查浏览器权限') }
}
watch(() => route.params.id, load)
onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-result v-if="loadError" icon="error" title="邮箱详情暂时无法加载" sub-title="请检查网络后重试"><template #extra><el-button type="primary" :loading="loading" @click="load">重新加载</el-button><el-button @click="router.push('/mailboxes')">返回邮箱</el-button></template></el-result>
    <div class="page-heading">
      <div>
        <el-button link class="back-button" @click="router.push('/mailboxes')">← 返回邮箱</el-button>
        <div class="mailbox-title-row"><h1>{{ mailbox?.email_address || '邮箱详情' }}</h1><el-button v-if="mailbox" link type="primary" @click.stop="copyMailboxInfo">复制邮箱</el-button></div>
        <p>{{ mailbox?.display_name || '接收邮箱' }} · 共 {{ emails.length }} 封邮件</p>
      </div>
      <div class="page-actions"><el-button v-if="mailbox" type="primary" @click="router.push({ path: '/outbound/new', query: { sender: mailbox.id } })">发送邮件</el-button><el-button :loading="loading" @click="load">刷新</el-button></div>
    </div>
    <el-card class="panel-card tag-assignment-card" shadow="never">
      <template #header><div class="card-header-row"><strong>邮箱标签</strong><span class="muted">标签使用稳定 ID 关联，修改名称不会丢失关系</span></div></template>
      <div class="tag-assignment">
        <el-select v-model="selectedTagIds" multiple filterable clearable placeholder="选择标签" class="tag-select" no-data-text="暂无标签，请先在标签管理创建">
          <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
        </el-select>
        <el-button type="primary" :loading="savingTags" :disabled="!mailbox" @click="saveTags">保存标签</el-button>
        <el-button @click="router.push('/tags')">管理标签</el-button>
      </div>
      <div v-if="selectedTagIds.length" class="selected-tags">
        <el-tag v-for="id in selectedTagIds" :key="id" effect="plain">{{ tags.find((tag) => tag.id === id)?.name || `#${id}` }}</el-tag>
      </div>
      <el-empty v-else :image-size="54" description="暂未添加标签" />
    </el-card>
    <el-card class="panel-card mail-list-card" shadow="never">
      <template #header><div class="card-header-row"><strong>邮件列表</strong><span class="muted">点击一行查看邮件详情</span></div></template>
        <el-table v-if="!loadError" v-loading="loading" :data="emails" stripe empty-text="暂无邮件" @row-click="openEmail">
        <el-table-column label="状态" width="85"><template #default="{ row }"><el-tag :type="row.is_read ? 'info' : 'warning'">{{ row.is_read ? '已读' : '未读' }}</el-tag></template></el-table-column>
        <el-table-column prop="sender" label="发件人" min-width="220" show-overflow-tooltip />
        <el-table-column prop="subject" label="主题" min-width="260" show-overflow-tooltip />
        <el-table-column label="验证码" width="130"><template #default="{ row }"><span v-if="row.verification_code" class="code-chip">{{ row.verification_code }}</span><span v-else class="muted">—</span></template></el-table-column>
        <el-table-column label="接收时间" min-width="190"><template #default="{ row }">{{ formatDate(row.received_at) }}</template></el-table-column>
        <el-table-column label="操作" width="100"><template #default="{ row }"><el-button link type="primary" :aria-label="`打开来自 ${row.sender} 的邮件`" @click.stop="openEmail(row)">打开</el-button></template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
