<script setup lang="ts">
import { Monitor, Moon, Sunny, Tickets } from '@element-plus/icons-vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { useTheme } from '../utils/theme'

const { theme, setTheme, options } = useTheme()
const open = ref(false)
function choose(value: typeof theme.value) { setTheme(value); open.value = false }
function onKey(event: KeyboardEvent) { if (event.key === 'Escape') open.value = false }
function onOutside(event: MouseEvent) { const target = event.target as Node; const root = document.querySelector('.theme-switcher'); if (root && !root.contains(target)) open.value = false }
onMounted(() => document.addEventListener('click', onOutside, true))
onBeforeUnmount(() => document.removeEventListener('click', onOutside, true))
</script>

<template>
  <div class="theme-switcher" aria-label="主题切换" @click.stop>
    <el-icon class="theme-switcher-icon"><Moon v-if="theme === 'dark'" /><Tickets v-else-if="theme === 'paper'" /><Monitor v-else-if="theme === 'system'" /><Sunny v-else /></el-icon>
    <el-button class="theme-toggle" size="small" :aria-expanded="open" aria-label="页面背景" @click="open = !open" @keydown="onKey">页面背景</el-button>
    <div v-if="open" class="theme-panel" role="dialog" aria-label="选择页面背景">
      <button v-for="option in options" :key="option.value" class="theme-option" :class="{ 'is-selected': theme === option.value }" :aria-pressed="theme === option.value" type="button" @click="choose(option.value)">
        <span class="theme-swatch" :data-theme-preview="option.value" aria-hidden="true" />
        <span>{{ option.label }}</span>
      </button>
    </div>
  </div>
</template>
