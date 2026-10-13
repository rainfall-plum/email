<script setup lang="ts">
import { isAuthFailure } from '../utils/session'
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorMessage, tagApi } from '../api'
import type { Tag } from '../types'

const tags = ref<Tag[]>([])
const name = ref('')
const loading = ref(false)
const creating = ref(false)
const renamingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)
const createVisible = ref(false)
const editVisible = ref(false)
const editingTag = ref<Tag | null>(null)
const editName = ref('')

async function load() { loading.value = true; try { tags.value = await tagApi.list() } catch (error) { if (!isAuthFailure(error)) ElMessage.error('标签加载失败，请稍后重试') } finally { loading.value = false } }
async function create() {
  if (creating.value) return
  if (!name.value.trim()) { ElMessage.warning('请输入标签名称'); return }
  creating.value = true
  try { await tagApi.create(name.value.trim()); name.value = ''; createVisible.value = false; ElMessage.success('标签已创建'); await load() }
  catch (error) { if (!isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '标签创建失败')) }
  finally { creating.value = false }
}
function openRename(tag: Tag) {
  if (renamingId.value !== null || deletingId.value !== null) return
  editingTag.value = tag; editName.value = tag.name; editVisible.value = true
}
async function rename() {
  if (!editingTag.value || renamingId.value !== null) return
  const value = editName.value.trim()
  if (!value) { ElMessage.warning('标签名称不能为空'); return }
  renamingId.value = editingTag.value.id
  try { await tagApi.update(editingTag.value.id, value); editVisible.value = false; ElMessage.success('标签已更新'); await load() }
  catch (error) { if (!isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '标签修改失败')) }
  finally { renamingId.value = null }
}
async function remove(tag: Tag) {
  if (renamingId.value !== null || deletingId.value !== null) return
  deletingId.value = tag.id
  try { await ElMessageBox.confirm(`确定删除标签“${tag.name}”？邮箱关联将被移除。`, '删除确认', { type: 'warning' }) }
  catch { deletingId.value = null; return }
  try { await tagApi.remove(tag.id); ElMessage.success('标签已删除'); await load() }
  catch (error) { if (!isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '标签删除失败')) }
  finally { deletingId.value = null }
}
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><h1>标签管理</h1><p>用标签整理接收邮箱；名称可以安全修改。</p></div><div class="page-actions"><el-button :loading="loading" @click="load">刷新</el-button><el-button type="primary" @click="createVisible = true">增加标签</el-button></div></div>
  <el-card class="panel-card" shadow="never"><div v-loading="loading" class="tag-grid"><div v-for="tag in tags" :key="tag.id" class="tag-management-card"><div class="tag-management-name">{{ tag.name }}</div><div class="muted">{{ tag.mailbox_count ?? 0 }} 个关联邮箱</div><div class="tag-management-actions"><el-button size="small" :loading="renamingId === tag.id" :disabled="deletingId !== null" @click="openRename(tag)">修改</el-button><el-button size="small" type="danger" plain :loading="deletingId === tag.id" :disabled="renamingId !== null" @click="remove(tag)">删除</el-button></div></div><el-empty v-if="!tags.length" description="暂无标签，先创建一个标签" /></div></el-card>
  <el-dialog v-model="createVisible" title="增加标签" width="min(420px, calc(100vw - 32px))" class="tag-dialog"><el-form @submit.prevent="create"><el-form-item label="标签名称" required><el-input v-model="name" maxlength="64" autofocus /></el-form-item><div class="dialog-form-submit"><el-button @click="createVisible = false">取消</el-button><el-button type="primary" native-type="submit" :loading="creating">创建</el-button></div></el-form></el-dialog>
  <el-dialog v-model="editVisible" title="修改标签" width="min(420px, calc(100vw - 32px))" class="tag-dialog"><el-form @submit.prevent="rename"><el-form-item label="标签名称" required><el-input v-model="editName" maxlength="64" autofocus /></el-form-item><div class="dialog-form-submit"><el-button :disabled="renamingId !== null" @click="editVisible = false">取消</el-button><el-button type="primary" native-type="submit" :loading="renamingId !== null">保存</el-button></div></el-form></el-dialog>
</template>
