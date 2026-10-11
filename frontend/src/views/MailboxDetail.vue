<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { mailboxApi, tagApi } from '../api'
import type { EmailItem, Mailbox, Tag } from '../types'

const route = useRoute(); const router = useRouter()
const emails = ref<EmailItem[]>([]); const loading = ref(false)
const mailbox = ref<Mailbox | null>(null)
const tags = ref<Tag[]>([])
const selectedTagIds = ref<number[]>([])
const savingTags = ref(false)
const mailboxId = computed(() => Number(route.params.id))
async function load() {
  loading.value = true
  try {
    const [mailboxData, emailData, tagData] = await Promise.all([
      mailboxApi.get(mailboxId.value), mailboxApi.emails(mailboxId.value), tagApi.list(),
    ])
    mailbox.value = mailboxData
    selectedTagIds.value = [...mailboxData.tag_ids]
    emails.value = emailData
    tags.value = tagData
  } catch { ElMessage.error('邮箱数据加载失败') } finally { loading.value = false }
}
async function saveTags() {
  if (!mailbox.value) return
  savingTags.value = true
  try {
    mailbox.value = await mailboxApi.update(mailbox.value.id, { tag_ids: selectedTagIds.value })
    ElMessage.success('标签已保存')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '标签保存失败')
  } finally { savingTags.value = false }
}
function openEmail(row: EmailItem) { router.push(`/emails/${row.id}`) }
onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="page-heading">
      <div>
        <el-button link class="back-button" @click="router.push('/mailboxes')">← 返回邮箱</el-button>
        <h1>{{ mailbox?.email_address || '邮箱详情' }}</h1>
        <p>{{ mailbox?.display_name || '接收邮箱' }} · 共 {{ emails.length }} 封邮件</p>
      </div>
      <el-button :loading="loading" @click="load">刷新</el-button>
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
      <el-table v-loading="loading" :data="emails" stripe empty-text="暂无邮件" @row-click="openEmail">
        <el-table-column label="状态" width="85"><template #default="{ row }"><el-tag :type="row.is_read ? 'info' : 'warning'">{{ row.is_read ? '已读' : '未读' }}</el-tag></template></el-table-column>
        <el-table-column prop="sender" label="发件人" min-width="220" show-overflow-tooltip />
        <el-table-column prop="subject" label="主题" min-width="260" show-overflow-tooltip />
        <el-table-column label="验证码" width="130"><template #default="{ row }"><span v-if="row.verification_code" class="code-chip">{{ row.verification_code }}</span><span v-else class="muted">—</span></template></el-table-column>
        <el-table-column prop="received_at" label="接收时间" min-width="190" />
      </el-table>
    </el-card>
  </div>
</template>
