import { validLocalSession } from './session'
export function sanitizeHtmlForPreview(html: string): string {
  if (typeof DOMParser === 'undefined') return ''
  const document = new DOMParser().parseFromString(html, 'text/html')
  const blocked = 'script,iframe,object,embed,frame,frameset,base,meta,link,form'
  document.querySelectorAll(blocked).forEach((element) => element.remove())
  document.querySelectorAll('*').forEach((element) => {
    for (const attribute of [...element.attributes]) {
      const name = attribute.name.toLowerCase()
      const value = attribute.value.trim().toLowerCase()
      if (name.startsWith('on') || name === 'srcdoc' || name === 'style' && /(url\s*\(|expression\s*\(|javascript\s*:)/i.test(value)) {
        element.removeAttribute(attribute.name)
      } else if (['href', 'src', 'xlink:href', 'poster', 'background'].includes(name)) {
        element.removeAttribute(attribute.name)
      }
    }
  })
  return document.body.innerHTML
}

export function hasAccessToken(): boolean {
  return validLocalSession()
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '暂无'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString('zh-CN')
}
