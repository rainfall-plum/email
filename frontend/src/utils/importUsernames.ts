export const IMPORT_MAX_BYTES = 1024 * 1024
export const IMPORT_MAX_COUNT = 1000
export const IMPORT_EXAMPLE = JSON.stringify({ usernames: ['alicewang', 'jacksmith88', 'testmail2026'] }, null, 2)
export function validateImportFile(file: File): string {
  if (!file.name.toLowerCase().endsWith('.json')) return '请选择 .json 文件'
  if (file.size > IMPORT_MAX_BYTES) return '文件不能超过 1 MiB'
  if (!file.size) return 'JSON 文件不能为空'
  return ''
}
export function parseImport(text: string): { error: string; invalid: number; total: number } {
  let value: unknown
  try { value = JSON.parse(text) } catch { return { error: 'JSON 解析失败，请检查文件格式', invalid: 0, total: 0 } }
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length !== 1 || !Array.isArray((value as { usernames?: unknown }).usernames)) {
    return { error: 'JSON 必须是仅包含 usernames 数组的对象', invalid: 0, total: 0 }
  }
  const names = (value as { usernames: unknown[] }).usernames
  if (!names.length || names.length > IMPORT_MAX_COUNT) return { error: 'usernames 数量必须为 1–1000 个', invalid: 0, total: names.length }
  return { error: '', total: names.length, invalid: names.filter(name => typeof name !== 'string' || !/^[a-z0-9]{1,64}$/.test(name)).length }
}
