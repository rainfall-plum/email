<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { HomeFilled, Menu, MessageBox, PriceTag, Setting, SwitchButton, Promotion } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { authApi } from './api'
import ThemeSwitcher from './components/ThemeSwitcher.vue'
import { LOGIN_MESSAGES, synchronizeSession, type LoginReason } from './utils/session'

const route = useRoute()
const router = useRouter()
const isLogin = computed(() => route.path === '/login')
const activeMenu = computed(() => route.path === '/outbound/new' ? '/outbound/new' : route.path.startsWith('/outbound') ? '/outbound' : route.path.startsWith('/mailboxes') || route.path.startsWith('/emails') ? '/mailboxes' : route.path)
const mobileNavOpen = ref(false)
watch(() => route.path, () => { mobileNavOpen.value = false })
watch(() => route.fullPath, () => { void nextTick(() => document.getElementById('main-content')?.focus()) })

async function logout() {
  try {
    await ElMessageBox.confirm('确认退出当前管理员账号吗？', '退出登录', {
      confirmButtonText: '退出登录',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
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
    <a class="skip-link" href="#main-content">跳转到主要内容</a>
    <el-aside width="224px" :class="['side-panel', { 'is-mobile-open': mobileNavOpen }]" :aria-hidden="!mobileNavOpen && undefined">
      <div class="brand" aria-label="Mailbox 管理平台">MAIL<span>BOX</span></div>
      <div class="brand-caption">管理员邮箱接收平台 · 内容与数据</div>
      <el-menu :default-active="activeMenu" router class="main-menu" aria-label="主导航" @select="mobileNavOpen = false">
        <el-menu-item index="/dashboard" aria-label="运行概览" title="运行概览"><el-icon><HomeFilled /></el-icon><span class="menu-label">Dashboard</span></el-menu-item>
        <el-menu-item index="/outbound/new" aria-label="发送邮箱" title="发送邮箱"><el-icon><Promotion /></el-icon><span class="menu-label">发送邮箱</span></el-menu-item>
        <el-menu-item index="/outbound" aria-label="发送记录" title="发送记录"><el-icon><Promotion /></el-icon><span class="menu-label">发送记录</span></el-menu-item>
        <el-menu-item index="/mailboxes" aria-label="邮箱管理" title="邮箱管理"><el-icon><MessageBox /></el-icon><span class="menu-label">邮箱管理</span></el-menu-item>
        <el-menu-item index="/tags" aria-label="标签管理" title="标签管理"><el-icon><PriceTag /></el-icon><span class="menu-label">标签管理</span></el-menu-item>
        <el-menu-item index="/settings" aria-label="系统设置" title="系统设置"><el-icon><Setting /></el-icon><span class="menu-label">系统设置</span></el-menu-item>
      </el-menu>
      <div class="side-footer">
        <button type="button" class="side-menu-action logout-button" aria-label="退出登录" title="退出登录" @click="logout"><el-icon><SwitchButton /></el-icon><span class="menu-label">退出登录</span></button>
        <span>邮箱管理</span>
      </div>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <div class="topbar-title"><el-button class="mobile-menu-button" text aria-label="打开主导航" title="打开主导航" @click="mobileNavOpen = !mobileNavOpen"><el-icon><Menu /></el-icon></el-button><span class="breadcrumb">{{ route.name || 'Email Platform' }}</span><span class="environment-pill">ADMIN · INBOX</span></div>
        <ThemeSwitcher />
      </el-header>
      <el-main id="main-content" class="content-area" tabindex="-1"><router-view /></el-main>
    </el-container>
  </el-container>
</template>
