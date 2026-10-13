<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, getApiErrorMessage } from '../api'
import { clearSession, isAuthFailure } from '../utils/session'

const username = ref('')
const loading = ref(false)
const saving = ref(false)
const failed = ref(false)
const changePassword = ref(false)
const form = reactive({ new_username: '', current_password: '', new_password: '', confirm_new_password: '' })
const errors = reactive({ new_username: '', current_password: '', new_password: '', confirm_new_password: '' })
function reset() {
  form.new_username = username.value; form.current_password = ''; form.new_password = ''; form.confirm_new_password = ''
  changePassword.value = false
  Object.keys(errors).forEach(key => { errors[key as keyof typeof errors] = '' })
}
async function load() {
  if (loading.value) return
  loading.value = true; failed.value = false
  try { username.value = (await adminApi.profile()).username; reset() }
  catch { failed.value = true }
  finally { loading.value = false }
}
function validate() {
  errors.current_password = form.current_password ? '' : '请输入当前密码'
  errors.new_username = /^[A-Za-z][A-Za-z0-9_]{2,63}$/.test(form.new_username) ? '' : '用户名须为 3–64 位，以字母开头，仅含字母、数字和下划线'
  errors.new_password = changePassword.value && (form.new_password.length < 4 || form.new_password.length > 128) ? '新密码须为 4–128 个字符' : ''
  errors.confirm_new_password = changePassword.value && form.new_password !== form.confirm_new_password ? '两次输入的新密码不一致' : ''
  if (Object.values(errors).some(Boolean)) return false
  if (form.new_username === username.value && !changePassword.value) { ElMessage.warning('请修改用户名或启用修改密码'); return false }
  return true
}
async function save() {
  if (saving.value || !validate()) return
  saving.value = true
  try {
    try { await ElMessageBox.confirm('修改管理员凭据后，所有已登录会话都会立即失效，需要使用新信息重新登录。确定继续吗？', '确认修改管理员信息', { confirmButtonText: '确认修改', cancelButtonText: '取消', type: 'warning' }) }
    catch { return }
    await adminApi.credentials({ current_password: form.current_password, ...(form.new_username !== username.value ? { new_username: form.new_username } : {}), ...(changePassword.value ? { new_password: form.new_password, confirm_new_password: form.confirm_new_password } : {}) })
    reset()
    clearSession('changed')
  } catch (cause) { if (!isAuthFailure(cause)) ElMessage.error(getApiErrorMessage(cause, '管理员信息修改失败，请检查当前密码和输入内容后重试')) }
  finally { saving.value = false; form.current_password = ''; form.new_password = ''; form.confirm_new_password = '' }
}
onMounted(load)
</script>

<template>
  <el-card class="panel-card account-card" shadow="never" v-loading="loading">
    <template #header><div><strong>管理员账户</strong><p class="muted">修改用户名或密码后，所有已登录会话立即失效。</p></div></template>
    <el-result v-if="failed" icon="error" title="管理员信息加载失败"><template #extra><el-button @click="load">重新加载账户</el-button></template></el-result>
    <template v-else>
      <p>当前管理员用户名：<strong>{{ username || '加载中' }}</strong></p>
      <el-form class="account-form" label-position="top" :disabled="saving || loading" @submit.prevent="save">
        <el-form-item label="新用户名" :error="errors.new_username"><el-input v-model="form.new_username" autocomplete="username" maxlength="64" aria-describedby="admin-name-rule" /><span id="admin-name-rule" class="muted">3–64 位，以字母开头，仅含字母、数字和下划线；保持原值可只修改密码。</span></el-form-item>
        <el-form-item label="当前密码" required :error="errors.current_password"><el-input v-model="form.current_password" type="password" show-password autocomplete="current-password" maxlength="128" /></el-form-item>
        <el-checkbox v-model="changePassword">修改密码</el-checkbox>
        <div v-if="changePassword" class="password-fields">
          <p id="admin-password-rule" class="muted">新密码须为 4–128 个字符。建议使用不易猜测的长密码，避免重复使用其他网站的密码。</p>
          <el-form-item label="新密码" required :error="errors.new_password"><el-input v-model="form.new_password" type="password" show-password autocomplete="new-password" maxlength="128" aria-describedby="admin-password-rule" /></el-form-item>
          <el-form-item label="确认新密码" required :error="errors.confirm_new_password"><el-input v-model="form.confirm_new_password" type="password" show-password autocomplete="new-password" maxlength="128" /></el-form-item>
        </div>
        <div class="account-actions"><el-button type="primary" :loading="saving" native-type="submit">保存管理员信息</el-button><el-button :disabled="saving" @click="reset">取消</el-button></div>
      </el-form>
    </template>
  </el-card>
</template>
