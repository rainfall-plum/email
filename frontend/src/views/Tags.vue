<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { tagApi } from '../api'
import type { Tag } from '../types'

const tags = ref<Tag[]>([]); const name = ref(''); const loading = ref(false)
async function load() { loading.value = true; try { tags.value = await tagApi.list() } catch { ElMessage.error('标签加载失败') } finally { loading.value = false } }
async function create() { if (!name.value.trim()) return; try { await tagApi.create(name.value.trim()); name.value = ''; ElMessage.success('标签已创建'); await load() } catch { ElMessage.error('标签创建失败') } }
async function rename(tag: Tag) { const result = await ElMessageBox.prompt('输入新的标签名称', '修改标签', { inputValue: tag.name }); try { await tagApi.update(tag.id, result.value); await load() } catch { ElMessage.error('标签修改失败') } }
async function remove(tag: Tag) { await ElMessageBox.confirm(`确定删除标签“${tag.name}”？`, '删除确认', { type: 'warning' }); try { await tagApi.remove(tag.id); ElMessage.success('标签已删除'); await load() } catch { ElMessage.error('标签删除失败') } }
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><h1>标签管理</h1><p>用标签整理接收邮箱</p></div></div><el-card class="panel-card"><el-form inline @submit.prevent="create"><el-form-item><el-input v-model="name" placeholder="新标签名称" @keyup.enter="create" /></el-form-item><el-form-item><el-button type="primary" @click="create">添加标签</el-button></el-form-item></el-form><el-divider /><el-table v-loading="loading" :data="tags"><el-table-column prop="name" label="标签名称" /><el-table-column prop="id" label="ID" width="100" /><el-table-column label="操作" width="180"><template #default="{ row }"><el-button link type="primary" @click="rename(row)">修改</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template></el-table-column></el-table></el-card>
</template>
