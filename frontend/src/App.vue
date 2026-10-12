<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { HomeFilled, MessageBox, PriceTag, Setting, SwitchButton, Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { authApi } from './api'
import ThemeSwitcher from './components/ThemeSwitcher.vue'
import { LOGIN_MESSAGES, synchronizeSession, type LoginReason } from './utils/session'

const route = useRoute()
const router = useRouter()
const isLogin = computed(() => route.path === '/login')
const activeMenu = computed(() => route.path.startsWith('/outbound') ? '/outbound' : route.path.startsWith('/mailboxes') || route.path.startsWith('/emails') ? '/mailboxes' : route.path)

function logout() {
  authApi.logout()
}
let redirecting = false
async function handleAuthExpired(event: Event) {
  if (isLogin.value || redirecting) return
  redirecting = true
  const reason = (event as CustomEvent<{ reason: LoginReason }>).detail?.reason || 'expired'
  if (LOGIN_MESSAGES[reason]) ElMessage.warning(LOGIN_MESSAGES[reason])
  try { await router.replace('/login') } finally { redirecting = false }
}
onMounted(() => { window.addEventListener('email-auth-expired', handleAuthExpired); window.addEventListener('storage', synchronizeSession) })
onBeforeUnmount(() => { window.removeEventListener('email-auth-expired', handleAuthExpired); window.removeEventListener('storage', synchronizeSession) })
</script>

<template>
  <router-view v-if="isLogin" />
  <el-container v-else class="app-shell">
    <el-aside width="224px" class="side-panel">
      <div class="brand">MAIL<span>BOX</span></div>
      <div class="brand-caption">管理员邮箱接收平台</div>
      <el-menu :default-active="activeMenu" router class="main-menu" aria-label="主导航">
        <el-menu-item index="/outbound" aria-label="发送记录" title="发送记录"><el-icon><Promotion /></el-icon><span class="menu-label">发送记录</span></el-menu-item>
        <el-menu-item index="/dashboard" aria-label="运行概览" title="运行概览"><el-icon><HomeFilled /></el-icon><span class="menu-label">Dashboard</span></el-menu-item>
        <el-menu-item index="/mailboxes" aria-label="邮箱管理" title="邮箱管理"><el-icon><MessageBox /></el-icon><span class="menu-label">邮箱管理</span></el-menu-item>
        <el-menu-item index="/tags" aria-label="标签管理" title="标签管理"><el-icon><PriceTag /></el-icon><span class="menu-label">标签管理</span></el-menu-item>
        <el-menu-item index="/settings" aria-label="系统设置" title="系统设置"><el-icon><Setting /></el-icon><span class="menu-label">系统设置</span></el-menu-item>
      </el-menu>
      <div class="side-footer">
        <el-button text class="logout-button" aria-label="退出登录" title="退出登录" @click="logout"><el-icon><SwitchButton /></el-icon><span class="menu-label">退出登录</span></el-button>
        <span>单域名 · 邮件管理</span>
      </div>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <div class="topbar-title"><span class="breadcrumb">{{ route.name || 'Email Platform' }}</span><span class="environment-pill">ADMIN</span></div>
        <ThemeSwitcher />
      </el-header>
      <el-main class="content-area"><router-view /></el-main>
    </el-container>
  </el-container>
</template>
