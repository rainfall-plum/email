<script setup lang="ts">
import { Moon, Sunny } from '@element-plus/icons-vue'

import { useTheme } from '../utils/theme'

const { theme, setTheme, options } = useTheme()
</script>

<template>
  <div class="theme-switcher" aria-label="主题切换">
    <el-icon class="theme-switcher-icon"><Moon v-if="theme === 'dark'" /><Sunny v-else /></el-icon>
    <el-select
      :model-value="theme"
      size="small"
      aria-label="选择主题"
      class="theme-select"
      @update:model-value="setTheme"
    >
      <el-option v-for="option in options" :key="option.value" :label="option.label" :value="option.value" />
    </el-select>
  </div>
</template>
