<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorMessage, mailboxApi, type ImportResult } from '../api'
import { IMPORT_EXAMPLE, parseImport, validateImportFile } from '../utils/importUsernames'
import { isAuthFailure } from '../utils/session'

const emit = defineEmits<{ imported: [] }>()
const visible = ref(false)
const file = ref<File | null>(null)
const input = ref<HTMLInputElement | null>(null)
const busy = ref(false)
const checking = ref(false)
const error = ref('')
const warning = ref('')
const result = ref<ImportResult | null>(null)
let selection = 0
function reset() { file.value = null; error.value = ''; warning.value = ''; result.value = null; if (input.value) input.value.value = '' }
function open() { if (busy.value) return; reset(); visible.value = true }
function download() {
  const url = URL.createObjectURL(new Blob([IMPORT_EXAMPLE], { type: 'application/json;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = 'usernames-example.json'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
async function choose(event: Event) {
  const selected = (event.target as HTMLInputElement).files?.[0]
  const current = ++selection
  reset()
  if (!selected) return
  error.value = validateImportFile(selected)
  if (error.value) return
  checking.value = true
  try {
    const buffer = await selected.arrayBuffer()
    const text = new TextDecoder('utf-8', { fatal: true }).decode(buffer)
    if (current !== selection) return
    const validation = parseImport(text)
    error.value = validation.error
    if (validation.error) return
    file.value = selected
    if (validation.invalid) warning.value = `发现 ${validation.invalid} 个格式不合法的用户名。导入时将跳过这些条目，并显示每项原因。`
  } catch { error.value = 'JSON 解析失败，请使用 UTF-8 编码的有效 JSON 文件' }
  finally { if (current === selection) checking.value = false }
}
async function submit() {
  if (busy.value || checking.value || !file.value) return
  busy.value = true; error.value = ''; result.value = null
  try {
    result.value = await mailboxApi.importUsernames(file.value)
    ElMessage.success(`导入完成，成功生成 ${result.value.success_count} 个邮箱`)
    emit('imported')
  } catch (cause) { if (!isAuthFailure(cause)) { error.value = getApiErrorMessage(cause, '导入失败，请检查文件并重试'); ElMessage.error(error.value) } }
  finally { busy.value = false }
}
function displayName(value: unknown) { return typeof value === 'string' ? value || '（空字符串）' : '（非字符串）' }
function poolCount(reason: string) { return result.value?.rejected_usernames.filter(item => item.reason === reason).length ?? 0 }
</script>

<template>
  <el-button @click="open">上传用户名 JSON</el-button>
  <el-dialog v-model="visible" title="上传用户名 JSON" width="min(760px, calc(100vw - 32px))" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy" :before-close="(done: () => void) => { if (!busy) done() }">
    <p id="import-rules">文件仅包含 <code>usernames</code> 字段（用户名字符串数组）。最多 1000 个用户名，文件不超过 1 MiB，使用 UTF-8 编码。用户名长度 1–64 位，只允许小写字母和数字，不能含空格。域名由系统配置决定。</p>
    <h3>JSON 格式示例</h3><pre class="json-example" aria-label="JSON 格式示例">{{ IMPORT_EXAMPLE }}</pre>
    <el-button @click="download">下载示例 JSON 文件</el-button>
    <div class="import-file-row"><label for="username-json-file">选择 JSON 文件</label><input id="username-json-file" ref="input" type="file" accept=".json,application/json" :disabled="busy || checking" aria-describedby="import-rules" @change="choose" /><span v-if="file" class="muted">已选择：{{ file.name }}</span></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <el-alert v-if="warning" :title="warning" type="warning" :closable="false" role="status" />
    <p v-if="checking" role="status">正在校验 JSON 文件…</p>
    <section v-if="result" class="import-result" aria-live="polite">
      <h3>导入结果</h3>
      <div class="import-stats"><span>总计 <strong>{{ result.total }}</strong></span><span>成功 <strong>{{ result.success_count }}</strong></span><span>重复 <strong>{{ result.duplicate_count }}</strong></span><span>已存在 <strong>{{ result.existing_count }}</strong></span><span>非法用户名 <strong>{{ result.invalid_count }}</strong></span></div>
      <p class="muted">已在可用池：{{ poolCount('already_available') }} · 已在使用池：{{ poolCount('already_used') }}。失败条目会跳过，其余有效条目一并提交；系统异常时本次有效条目整体回滚。</p>
      <el-table v-if="result.rejected_usernames.length" :data="result.rejected_usernames" max-height="280" aria-label="失败用户名及原因"><el-table-column label="用户名" min-width="150"><template #default="{ row }"><span class="rejected-name">{{ displayName(row.username) }}</span></template></el-table-column><el-table-column prop="reason" label="分类" min-width="150" /><el-table-column prop="message" label="失败原因" min-width="230" /></el-table>
      <el-table v-if="result.created_mailboxes.length" :data="result.created_mailboxes" max-height="220" aria-label="成功生成的邮箱"><el-table-column prop="email" label="成功生成的邮箱" min-width="260" /></el-table>
    </section>
    <template #footer><el-button :disabled="busy || checking" @click="reset">重新上传</el-button><el-button :disabled="busy" @click="visible = false">关闭</el-button><el-button type="primary" :loading="busy" :disabled="!file || checking" @click="submit">开始导入</el-button></template>
  </el-dialog>
</template>
