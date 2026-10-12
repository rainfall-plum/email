<script setup lang="ts">
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

async function load() { loading.value = true; try { tags.value = await tagApi.list() } catch { ElMessage.error('标签加载失败，请稍后重试') } finally { loading.value = false } }
async function create() {
  if (!name.value.trim()) { ElMessage.warning('请输入标签名称'); return }
  creating.value = true
  try { await tagApi.create(name.value.trim()); name.value = ''; ElMessage.success('标签已创建'); await load() }
  catch (error) { ElMessage.error(getApiErrorMessage(error, '标签创建失败')) }
  finally { creating.value = false }
}
async function rename(tag: Tag) {
  let result: { value: string }
  try { result = await ElMessageBox.prompt('输入新的标签名称', '修改标签', { inputValue: tag.name }) }
  catch { return }
  if (!result.value.trim()) { ElMessage.warning('标签名称不能为空'); return }
  renamingId.value = tag.id
  try { await tagApi.update(tag.id, result.value.trim()); ElMessage.success('标签已更新'); await load() }
  catch (error) { ElMessage.error(getApiErrorMessage(error, '标签修改失败')) }
  finally { renamingId.value = null }
}
async function remove(tag: Tag) {
  try { await ElMessageBox.confirm(`确定删除标签“${tag.name}”？邮箱关联将被移除。`, '删除确认', { type: 'warning' }) }
  catch { return }
  deletingId.value = tag.id
  try { await tagApi.remove(tag.id); ElMessage.success('标签已删除'); await load() }
  catch (error) { ElMessage.error(getApiErrorMessage(error, '标签删除失败')) }
  finally { deletingId.value = null }
}
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><h1>标签管理</h1><p>用标签整理接收邮箱；标签 ID 稳定，名称可以安全修改。</p></div><el-button :loading="loading" @click="load">刷新</el-button></div>
  <el-card class="panel-card" shadow="never"><el-form class="inline-form" @submit.prevent="create"><el-form-item><el-input v-model="name" placeholder="新标签名称" @keyup.enter="create" /></el-form-item><el-form-item><el-button type="primary" :loading="creating" native-type="submit">添加标签</el-button></el-form-item></el-form><el-divider /><el-table v-loading="loading" :data="tags" empty-text="暂无标签"><el-table-column prop="name" label="标签名称" min-width="220" /><el-table-column prop="id" label="稳定 ID" width="110" /><el-table-column label="操作" width="180"><template #default="{ row }"><el-button link type="primary" :loading="renamingId === row.id" :disabled="deletingId === row.id" @click="rename(row)">修改</el-button><el-button link type="danger" :loading="deletingId === row.id" :disabled="renamingId === row.id" @click="remove(row)">删除</el-button></template></el-table-column></el-table></el-card>
</template>
