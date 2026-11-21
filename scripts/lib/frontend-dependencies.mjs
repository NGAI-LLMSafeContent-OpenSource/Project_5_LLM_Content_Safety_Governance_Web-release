import fs from 'node:fs'
import path from 'node:path'

export function hasNodeModules(cwd, options = {}) {
  const existsSync = options.existsSync ?? fs.existsSync
  return existsSync(path.join(cwd, 'node_modules'))
}
