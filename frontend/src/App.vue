<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { HomeFilled, MessageBox, PriceTag, Setting, SwitchButton } from '@element-plus/icons-vue'

import { authApi } from './api'

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
      <el-menu :default-active="route.path" router class="main-menu">
        <el-menu-item index="/dashboard"><el-icon><HomeFilled /></el-icon>Dashboard</el-menu-item>
        <el-menu-item index="/mailboxes"><el-icon><MessageBox /></el-icon>邮箱管理</el-menu-item>
        <el-menu-item index="/tags"><el-icon><PriceTag /></el-icon>标签管理</el-menu-item>
      </el-menu>
      <div class="side-footer">
        <el-button text @click="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-button>
        <span><el-icon><Setting /></el-icon> Local Development</span>
      </div>
    </el-aside>
    <el-container>
      <el-header class="topbar"><span class="breadcrumb">{{ route.name || 'Email Platform' }}</span><span class="environment-pill">TEST ENV</span></el-header>
      <el-main class="content-area"><router-view /></el-main>
    </el-container>
  </el-container>
</template>
