/** 是否为有效的中文名 */
export function isValidName(name: string): boolean {
  return /^[一-龥a-zA-Z0-9_\s]{1,50}$/.test(name)
}

/** 是否为有效的描述文本 */
export function isValidDescription(desc: string, maxLength = 500): boolean {
  return desc.length > 0 && desc.length <= maxLength
}
