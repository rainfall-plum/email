<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { authApi, getApiErrorMessage } from '../api'
import ThemeSwitcher from '../components/ThemeSwitcher.vue'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function submit() {
  if (loading.value) return
  if (!form.username || !form.password) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try {
    await authApi.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '登录服务暂不可用，请稍后重试'))
  } finally { loading.value = false; form.password = '' }
}
</script>

<template>
  <div class="login-page">
    <div class="login-theme"><ThemeSwitcher /></div>
    <el-card class="login-card">
      <h1 class="login-brand">MAIL<span>BOX</span></h1>
      <div class="login-subtitle">单域名管理员邮箱接收平台</div>
      <el-form @submit.prevent="submit" label-position="top">
        <el-form-item label="管理员用户名"><el-input v-model="form.username" autocomplete="username" placeholder="输入管理员用户名" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password autocomplete="current-password" placeholder="输入密码" /></el-form-item>
        <el-button type="primary" class="w-full" :loading="loading" native-type="submit">登录后台</el-button>
      </el-form>
    </el-card>
  </div>
</template>
