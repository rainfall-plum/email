import { beforeEach, describe, expect, it } from 'vitest'

import { hasAccessToken, sanitizeHtmlForPreview } from '../utils/email'
import { initializeTheme, THEME_OPTIONS, useTheme } from '../utils/theme'

describe('frontend safety helpers', () => {
  beforeEach(() => localStorage.clear())

  it('removes executable HTML content for sandbox preview', () => {
    const result = sanitizeHtmlForPreview(
      '<p onclick="alert(1)">code</p><script>alert(2)</script><iframe src="evil"></iframe><a href="javascript:alert(3)">x</a>',
    )
    expect(result).toBe('<p>code</p><a>x</a>')
  })

  it('detects the local JWT session token', () => {
    expect(hasAccessToken()).toBe(false)
    localStorage.setItem('email_access_token', 'test-token')
    expect(hasAccessToken()).toBe(true)
  })

  it('offers all supported themes and persists the selected theme', () => {
    expect(THEME_OPTIONS.map((option) => option.value)).toEqual(['system', 'dark', 'white', 'paper'])

    initializeTheme()
    const { theme, setTheme } = useTheme()
    setTheme('paper')

    expect(theme.value).toBe('paper')
    expect(localStorage.getItem('email_theme_mode')).toBe('paper')
    expect(document.documentElement.dataset.theme).toBe('paper')

    setTheme('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
