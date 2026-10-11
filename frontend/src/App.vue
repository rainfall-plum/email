<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { HomeFilled, MessageBox, PriceTag, Setting, SwitchButton } from '@element-plus/icons-vue'

import { authApi } from './api'
import ThemeSwitcher from './components/ThemeSwitcher.vue'

const route = useRoute()
const router = useRouter()
const isLogin = computed(() => route.path === '/login')

function logout() {
  authApi.logout()
  router.push('/login')
}
</script>

<template>
  <router-view v-if="isLogin" />
  <el-container v-else class="app-shell">
    <el-aside width="224px" class="side-panel">
      <div class="brand">MAIL<span>BOX</span></div>
      <div class="brand-caption">管理员邮箱接收平台</div>
      <el-menu :default-active="route.path" router class="main-menu" aria-label="主导航">
        <el-menu-item index="/dashboard" aria-label="运行概览"><el-icon><HomeFilled /></el-icon>Dashboard</el-menu-item>
        <el-menu-item index="/mailboxes" aria-label="邮箱管理"><el-icon><MessageBox /></el-icon>邮箱管理</el-menu-item>
        <el-menu-item index="/tags" aria-label="标签管理"><el-icon><PriceTag /></el-icon>标签管理</el-menu-item>
        <el-menu-item index="/settings" aria-label="系统设置"><el-icon><Setting /></el-icon>系统设置</el-menu-item>
      </el-menu>
      <div class="side-footer">
        <el-button text class="logout-button" @click="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-button>
        <span>单域名 · 只接收邮件</span>
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
