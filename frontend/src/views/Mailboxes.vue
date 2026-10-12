<script setup lang="ts">
import { isAuthFailure } from '../utils/session'
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { getApiErrorMessage, mailboxApi, tagApi } from '../api'
import type { Mailbox, Tag } from '../types'
import { formatDate } from '../utils/email'
import UsernameImport from '../components/UsernameImport.vue'

const router = useRouter()
const mailboxes = ref<Mailbox[]>([])
const tags = ref<Tag[]>([])
const loading = ref(false)
const createLoading = ref(false)
const batchLoading = ref(false)
const deleteLoadingId = ref<number | null>(null)
const createVisible = ref(false)
const batchVisible = ref(false)
const form = reactive({ local_part: '', display_name: '', tag_ids: [] as number[] })
const batchTagIds = ref<number[]>([])
const count = ref(100)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filters = reactive({ tag_ids: [] as number[], tag_mode: 'any' as 'any' | 'all', untagged: false, sort_by: 'created_desc' })

const dialogWidth = 'min(500px, calc(100vw - 32px))'
let loadSequence = 0

async function load() {
  const sequence = ++loadSequence
  loading.value = true
  try {
    const [result, tagData] = await Promise.all([
      mailboxApi.list({ page: page.value, page_size: pageSize.value, ...filters }),
      tagApi.list(),
    ])
    if (sequence !== loadSequence) return
    if (page.value > Math.max(1, result.pages)) { page.value = Math.max(1, result.pages); void load(); return }
    mailboxes.value = result.items
    total.value = result.total
    tags.value = tagData
  } catch (error) { if (sequence === loadSequence && !isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '邮箱数据加载失败，请稍后重试')) } finally { if (sequence === loadSequence) loading.value = false }
}
function resetPageAndLoad() { page.value = 1; void load() }
function onTagsChange() { if (filters.tag_ids.length) filters.untagged = false; resetPageAndLoad() }
function onUntaggedChange() { if (filters.untagged) filters.tag_ids = []; resetPageAndLoad() }
function tagName(id: number) { return tags.value.find((tag) => tag.id === id)?.name || `#${id}` }
function openMailbox(id: number) { router.push(`/mailboxes/${id}`) }

async function create() {
  if (createLoading.value) return
  createLoading.value = true
  try {
    await mailboxApi.create(form)
    ElMessage.success('邮箱创建成功')
    createVisible.value = false
    form.local_part = ''; form.display_name = ''; form.tag_ids = []
    await load()
  } catch (error) { if (!isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '邮箱创建失败')) }
  finally { createLoading.value = false }
}
async function batch() {
  if (batchLoading.value) return
  batchLoading.value = true
  try {
    const result = await mailboxApi.batch(count.value, batchTagIds.value)
    ElMessage.success(`成功生成 ${result.mailboxes.length} 个邮箱`)
    batchVisible.value = false; batchTagIds.value = []
    page.value = 1
    await load()
  } catch (error) { if (!isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '批量生成失败')) }
  finally { batchLoading.value = false }
}
async function remove(mailbox: Mailbox) {
  try { await ElMessageBox.confirm(`确定删除 ${mailbox.email_address}？邮件和附件记录也会被删除。`, '删除确认', { type: 'warning' }) }
  catch { return }
  deleteLoadingId.value = mailbox.id
  try { await mailboxApi.remove(mailbox.id); ElMessage.success('邮箱已删除'); await load() }
  catch (error) { if (!isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '删除失败，请稍后重试')) }
  finally { deleteLoadingId.value = null }
}
function onPageSizeChange(size: number) { pageSize.value = size; page.value = 1; void load() }
function onPageChange(nextPage: number) { page.value = nextPage; void load() }
onMounted(load)
</script>

<template>
  <div class="page-heading">
    <div><h1>邮箱管理</h1><p>筛选、排序并管理单域名接收邮箱</p></div>
    <div class="page-actions"><UsernameImport @imported="resetPageAndLoad" /><el-button @click="batchVisible = true">批量生成</el-button><el-button type="primary" @click="createVisible = true">创建邮箱</el-button></div>
  </div>
  <el-card class="panel-card filter-card" shadow="never">
    <div class="filter-grid">
      <el-form-item label="标签"><el-select v-model="filters.tag_ids" multiple filterable clearable placeholder="全部标签" @change="onTagsChange"><el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" /></el-select></el-form-item>
      <el-form-item v-if="filters.tag_ids.length" label="匹配"><el-radio-group v-model="filters.tag_mode" @change="resetPageAndLoad"><el-radio-button value="any">任一标签</el-radio-button><el-radio-button value="all">全部标签</el-radio-button></el-radio-group></el-form-item>
      <el-checkbox v-model="filters.untagged" @change="onUntaggedChange">只看无标签</el-checkbox>
      <el-form-item label="排序"><el-select v-model="filters.sort_by" @change="resetPageAndLoad"><el-option label="创建时间：最新" value="created_desc" /><el-option label="创建时间：最旧" value="created_asc" /><el-option label="最新邮件：最新" value="latest_email_desc" /><el-option label="最早邮件：最早" value="oldest_email_asc" /><el-option label="未读优先" value="unread_desc" /><el-option label="邮箱地址：A-Z" value="email_asc" /><el-option label="邮箱地址：Z-A" value="email_desc" /></el-select></el-form-item>
      <el-button @click="load" :loading="loading">刷新</el-button>
    </div>
  </el-card>
  <el-card class="panel-card" shadow="never">
    <el-table v-loading="loading" :data="mailboxes" stripe empty-text="没有符合条件的邮箱">
      <el-table-column label="邮箱地址" min-width="250"><template #default="{ row }"><el-link type="primary" class="mailbox-link" @click="openMailbox(row.id)">{{ row.email_address }}</el-link></template></el-table-column>
      <el-table-column prop="display_name" label="显示名称" min-width="130" show-overflow-tooltip />
      <el-table-column label="标签" min-width="180"><template #default="{ row }"><el-tag v-for="id in row.tag_ids" :key="id" size="small" class="table-tag">{{ tagName(id) }}</el-tag><span v-if="row.tag_ids.length === 0" class="muted">无</span></template></el-table-column>
      <el-table-column label="邮件" width="120"><template #default="{ row }">{{ row.email_count }} 封<span v-if="row.unread_count" class="unread-count"> · {{ row.unread_count }} 未读</span></template></el-table-column>
      <el-table-column label="最新邮件" min-width="170"><template #default="{ row }">{{ formatDate(row.latest_email_at) }}</template></el-table-column>
      <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="190" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openMailbox(row.id)">查看邮件</el-button><el-button link type="danger" :loading="deleteLoadingId === row.id" @click="remove(row)">删除</el-button></template></el-table-column>
    </el-table>
    <div class="table-footer"><span class="muted">共 {{ total }} 个邮箱</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20, 50, 100]" layout="sizes, prev, pager, next" @size-change="onPageSizeChange" @current-change="onPageChange" /></div>
  </el-card>
  <el-dialog v-model="createVisible" title="创建邮箱" :width="dialogWidth"><el-form label-position="top"><el-form-item label="邮箱前缀" required><el-input v-model="form.local_part" placeholder="只允许小写字母和数字" /></el-form-item><el-form-item label="显示名称"><el-input v-model="form.display_name" /></el-form-item><el-form-item label="标签"><el-select v-model="form.tag_ids" multiple style="width: 100%"><el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" /></el-select></el-form-item></el-form><template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="createLoading" @click="create">创建</el-button></template></el-dialog>
  <el-dialog v-model="batchVisible" title="批量生成邮箱" :width="dialogWidth"><p class="muted">系统将从 JSON 名字库生成邮箱，单次最多生成 1000 个。</p><el-form label-position="top"><el-form-item label="生成数量"><el-input-number v-model="count" :min="1" :max="1000" /></el-form-item><el-form-item label="统一标签"><el-select v-model="batchTagIds" multiple filterable clearable placeholder="可选" style="width: 100%"><el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" /></el-select></el-form-item></el-form><template #footer><el-button @click="batchVisible = false">取消</el-button><el-button type="primary" :loading="batchLoading" @click="batch">开始生成</el-button></template></el-dialog>
</template>
