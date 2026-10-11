export function sanitizeHtmlForPreview(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+\s*=\s*(["']).*?\1/gi, '')
    .replace(/\s(?:href|src)\s*=\s*(["'])\s*javascript:[\s\S]*?\1/gi, '')
}

export function hasAccessToken(): boolean {
  return Boolean(localStorage.getItem('email_access_token'))
}
