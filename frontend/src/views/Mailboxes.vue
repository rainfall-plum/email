<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { mailboxApi, tagApi } from '../api'
import type { Mailbox, Tag } from '../types'

const router = useRouter()
const mailboxes = ref<Mailbox[]>([])
const tags = ref<Tag[]>([])
const loading = ref(false)
const createVisible = ref(false)
const batchVisible = ref(false)
const form = reactive({ local_part: '', display_name: '', tag_ids: [] as number[] })
const count = ref(100)

async function load() {
  loading.value = true
  try { [mailboxes.value, tags.value] = await Promise.all([mailboxApi.list(), tagApi.list()]) }
  catch { ElMessage.error('邮箱数据加载失败') } finally { loading.value = false }
}
async function create() {
  try { await mailboxApi.create(form); ElMessage.success('邮箱创建成功'); createVisible.value = false; form.local_part = ''; form.display_name = ''; form.tag_ids = []; await load() }
  catch (error: any) { ElMessage.error(error.response?.data?.detail || '邮箱创建失败') }
}
async function batch() {
  try { const result = await mailboxApi.batch(count.value); ElMessage.success(`成功生成 ${result.mailboxes.length} 个邮箱`); batchVisible.value = false; await load() }
  catch (error: any) { ElMessage.error(error.response?.data?.detail || '批量生成失败') }
}
async function remove(mailbox: Mailbox) {
  await ElMessageBox.confirm(`确定删除 ${mailbox.email_address}？邮件和附件记录也会被删除。`, '删除确认', { type: 'warning' })
  try { await mailboxApi.remove(mailbox.id); ElMessage.success('邮箱已删除'); await load() } catch { ElMessage.error('删除失败') }
}
function tagName(id: number) { return tags.value.find((tag) => tag.id === id)?.name || `#${id}` }
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><h1>邮箱管理</h1><p>创建并管理单域名接收邮箱</p></div><div><el-button @click="batchVisible = true">批量生成</el-button><el-button type="primary" @click="createVisible = true">创建邮箱</el-button></div></div>
  <el-card class="panel-card"><el-table v-loading="loading" :data="mailboxes" stripe><el-table-column prop="email_address" label="邮箱地址" min-width="250"><template #default="{ row }"><el-link type="primary" @click="router.push(`/mailboxes/${row.id}`)">{{ row.email_address }}</el-link></template></el-table-column><el-table-column prop="display_name" label="显示名称" /><el-table-column label="标签"><template #default="{ row }"><el-tag v-for="id in row.tag_ids" :key="id" size="small" style="margin-right: 4px">{{ tagName(id) }}</el-tag><span v-if="!row.tag_ids" class="muted">无</span></template></el-table-column><el-table-column label="状态"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column><el-table-column prop="created_source" label="来源" /><el-table-column label="操作" width="150"><template #default="{ row }"><el-button link type="primary" @click="router.push(`/mailboxes/${row.id}`)">查看邮件</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template></el-table-column></el-table></el-card>
  <el-dialog v-model="createVisible" title="创建邮箱" width="500px"><el-form label-position="top"><el-form-item label="邮箱前缀"><el-input v-model="form.local_part" placeholder="只允许 a-z、0-9" /></el-form-item><el-form-item label="显示名称"><el-input v-model="form.display_name" /></el-form-item><el-form-item label="标签"><el-select v-model="form.tag_ids" multiple style="width: 100%"><el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" /></el-select></el-form-item></el-form><template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" @click="create">创建</el-button></template></el-dialog>
  <el-dialog v-model="batchVisible" title="批量生成邮箱" width="420px"><p class="muted">系统将从本地 JSON 名字库生成邮箱，开发名字库支持最多 100 个测试邮箱。</p><el-input-number v-model="count" :min="1" :max="1000" /><template #footer><el-button @click="batchVisible = false">取消</el-button><el-button type="primary" @click="batch">开始生成</el-button></template></el-dialog>
</template>
