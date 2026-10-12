import { ref } from 'vue'

export type ThemeMode = 'dark' | 'white' | 'paper' | 'system'

export const THEME_OPTIONS: Array<{ value: ThemeMode; label: string }> = [
  { value: 'system', label: '跟随系统' },
  { value: 'dark', label: '暗色' },
  { value: 'white', label: '纯白' },
  { value: 'paper', label: '羊毛纸' },
]

const STORAGE_KEY = 'email_theme_mode'
const theme = ref<ThemeMode>(readTheme())
let mediaQuery: MediaQueryList | null = null

function readTheme(): ThemeMode {
  const value = localStorage.getItem(STORAGE_KEY)
  return value === 'dark' || value === 'white' || value === 'paper' || value === 'system'
    ? value
    : 'system'
}
function applyTheme(value: ThemeMode) {
  document.documentElement.dataset.theme = value
}

export function initializeTheme() {
  applyTheme(theme.value)
  mediaQuery ??= window.matchMedia?.('(prefers-color-scheme: dark)') ?? null
  mediaQuery?.addEventListener('change', () => {
    if (theme.value === 'system') applyTheme('system')
  })
}

export function useTheme() {
  function setTheme(value: ThemeMode) {
    theme.value = value
    localStorage.setItem(STORAGE_KEY, value)
    applyTheme(value)
  }

  return { theme, setTheme, options: THEME_OPTIONS }
}

// Theme utilities intentionally share one persisted mode across every page.
