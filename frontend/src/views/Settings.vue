<script setup lang="ts">
import { isAuthFailure } from '../utils/session'
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getApiErrorMessage, settingsApi } from '../api'
import type { SystemSetting } from '../types'
import AdminAccount from '../components/AdminAccount.vue'

const settings = ref<SystemSetting[]>([])
const drafts = ref<Record<string, string>>({})
const loading = ref(false)
const savingKey = ref<string | null>(null)
const activeTab = ref<'config' | 'account'>('config')

async function load() {
  loading.value = true
  try {
    settings.value = await settingsApi.list()
    drafts.value = Object.fromEntries(settings.value.map((item) => [item.key, item.value]))
  } catch (error) { if (!isAuthFailure(error)) ElMessage.error('配置加载失败，请稍后重试') } finally { loading.value = false }
}
async function save(item: SystemSetting) {
  if (!item.editable || savingKey.value !== null) return
  savingKey.value = item.key
  try { await ElMessageBox.confirm(`确认保存“${item.label}”的新值吗？`, '保存配置', { type: 'warning' }) }
  catch { savingKey.value = null; return }
  savingKey.value = item.key
  try { const updated = await settingsApi.update(item.key, drafts.value[item.key] ?? ''); settings.value = settings.value.map((value) => value.key === item.key ? updated : value); ElMessage.success('配置已保存') }
  catch (error) { if (!isAuthFailure(error)) ElMessage.error(getApiErrorMessage(error, '配置保存失败')) }
  finally { savingKey.value = null }
}
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><h1>系统设置</h1><p>仅展示安全白名单配置；敏感密钥和服务器路径不会显示。</p></div><el-button :loading="loading" @click="load">刷新配置</el-button></div>
  <el-tabs v-model="activeTab" class="settings-tabs" type="card" aria-label="设置分区">
    <el-tab-pane label="配置修改" name="config">
  <el-card class="panel-card" shadow="never">
    <el-table v-loading="loading" :data="settings" empty-text="暂无可用配置">
      <el-table-column prop="label" label="配置项" min-width="220" />
      <el-table-column label="当前值" min-width="240"><template #default="{ row }"><el-input-number v-if="row.editable && row.key === 'max_emails_per_mailbox'" :model-value="Number(drafts[row.key])" :aria-label="`当前值：${row.label}`" :min="1" :max="100" :disabled="savingKey === row.key" @update:model-value="(value: number | undefined) => drafts[row.key] = String(value ?? '')" /><el-input v-else-if="row.editable" v-model="drafts[row.key]" :aria-label="`当前值：${row.label}`" :disabled="savingKey === row.key" /><span v-else class="setting-readonly">{{ row.value }}</span></template></el-table-column>
      <el-table-column label="说明" min-width="180"><template #default="{ row }"><el-tag v-if="row.editable" type="success">可在线修改</el-tag><el-tag v-else type="info">只读</el-tag><span v-if="row.requires_restart" class="muted setting-note">修改后需重启</span></template></el-table-column>
      <el-table-column label="操作" width="120"><template #default="{ row }"><el-button v-if="row.editable" type="primary" size="small" :loading="savingKey === row.key" @click="save(row)">保存</el-button><span v-else class="muted">—</span></template></el-table-column>
    </el-table>
  </el-card>
    </el-tab-pane>
    <el-tab-pane label="密码修改" name="account">
      <AdminAccount />
    </el-tab-pane>
  </el-tabs>
</template>
