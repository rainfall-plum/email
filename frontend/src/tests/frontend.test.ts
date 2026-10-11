import { beforeEach, describe, expect, it } from 'vitest'

import { hasAccessToken, sanitizeHtmlForPreview } from '../utils/email'

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
})
