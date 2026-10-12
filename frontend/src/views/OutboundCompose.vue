<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { outboundApi, getApiErrorMessage } from '../api'
import type { OutboundDraft } from '../types'
import { validateOutbound } from '../utils/outbound'

const route = useRoute(); const router = useRouter()
const options = ref<{ id: number; email_address: string }[]>([])
const loading = ref(false); const submitting = ref(false); const loadError = ref(false)
const draft = reactive<OutboundDraft>({ sender_mailbox_id: undefined, recipient: '', subject: '', body_text: '', idempotency_key: crypto.randomUUID() })
// Preserve exactly the submitted payload after an uncertain network result; repeat uses the same key.
const pending = ref<OutboundDraft | null>(null)
const errors = ref({ sender_mailbox_id: '', recipient: '', subject: '', body_text: '' })
function validate() { errors.value = validateOutbound(draft); return !Object.values(errors.value).some(Boolean) }
async function load() {
  loading.value = true; loadError.value = false
  try {
    options.value = await outboundApi.options()
    const selected = Number(route.query.sender)
    if (options.value.some(item => item.id === selected)) draft.sender_mailbox_id = selected
  } catch { loadError.value = true } finally { loading.value = false }
}
async function submit() {
  if (submitting.value) return
  submitting.value = true
  try {
    if (!pending.value && !validate()) return
    pending.value ??= { ...draft, recipient: draft.recipient.trim() }
    await outboundApi.create(pending.value)
    ElMessage.success('发送任务已创建')
    await router.push('/outbound')
  } catch (error) {
    const status = (error as { response?: { status?: number } }).response?.status
    if (status && status >= 400 && status < 500) pending.value = null
    ElMessage.error(getApiErrorMessage(error, '提交未确认，请重试确认原任务，避免重复发送'))
  } finally { submitting.value = false }
}
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><h1>发送邮件</h1><p>仅支持纯文本，不支持 HTML 和附件。每封邮件仅限一个收件人。</p></div></div>
  <el-card class="panel-card compose-card" shadow="never" v-loading="loading">
    <el-result v-if="loadError" icon="error" title="发件邮箱加载失败"><template #extra><el-button @click="load">重新加载</el-button></template></el-result>
    <el-empty v-else-if="!loading && !options.length" description="暂无系统邮箱，请先创建邮箱" />
    <el-form v-else :model="draft" label-position="top" :disabled="submitting || !!pending" @submit.prevent="submit">
      <el-form-item label="发件人" prop="sender_mailbox_id" :error="errors.sender_mailbox_id"><el-select v-model="draft.sender_mailbox_id" filterable placeholder="选择系统已有邮箱" class="w-full"><el-option v-for="item in options" :key="item.id" :label="item.email_address" :value="item.id" /></el-select></el-form-item>
      <el-form-item label="收件人" prop="recipient" :error="errors.recipient"><el-input v-model="draft.recipient" maxlength="254" placeholder="一个外部邮箱地址" /></el-form-item>
      <el-form-item label="主题" prop="subject" :error="errors.subject"><el-input v-model="draft.subject" maxlength="200" show-word-limit /></el-form-item>
      <el-form-item label="纯文本正文" prop="body_text" :error="errors.body_text"><el-input v-model="draft.body_text" type="textarea" :rows="10" maxlength="100000" show-word-limit /></el-form-item>
    </el-form>
    <p v-if="pending && !submitting" role="status">上次提交结果未确认，表单已锁定。请点击“确认原任务”，使用相同提交标识安全查询或重试。</p>
    <div class="page-actions"><el-button type="primary" :loading="submitting" :disabled="loading || loadError || !options.length" @click="submit">{{ pending ? '确认原任务' : '提交发送' }}</el-button><el-button :disabled="submitting" @click="router.push('/outbound')">取消</el-button></div>
  </el-card>
</template>
