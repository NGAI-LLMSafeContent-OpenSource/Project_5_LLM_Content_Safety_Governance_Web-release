import { existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const repoRoot = join(frontendRoot, '../..')
const hooksPath = spawnSync('git', ['config', '--local', '--get', 'core.hooksPath'], {
  cwd: repoRoot,
  encoding: 'utf8',
})
const expectedPath = '.husky/_'
const hookRunner = join(repoRoot, expectedPath, 'pre-commit')
const hookScript = join(repoRoot, '.husky/pre-commit')

const errors = []

if (hooksPath.error) {
  errors.push(`git 命令执行失败: ${hooksPath.error.message}`)
  errors.push('请确认已安装 git 且当前目录为 git 仓库')
} else if (hooksPath.status !== 0) {
  errors.push(`本仓库未设置 local core.hooksPath（当前: ${hooksPath.stdout.trim() || '(未设置)'}）`)
  errors.push('请执行: cd web/frontend && pnpm install')
} else {
  const configuredPath = hooksPath.stdout.trim()
  if (configuredPath !== expectedPath) {
    errors.push(
      `local core.hooksPath 应为 "${expectedPath}"，当前为 "${configuredPath || '(未设置)'}"`,
    )
    errors.push('请执行: cd web/frontend && pnpm install')
  }
}

if (!existsSync(hookRunner)) {
  errors.push(`缺少 ${expectedPath}/pre-commit，请执行: cd web/frontend && pnpm install`)
}

if (!existsSync(hookScript)) {
  errors.push('缺少 .husky/pre-commit')
}

if (!existsSync(join(frontendRoot, 'node_modules/.bin/lint-staged'))) {
  errors.push('缺少 lint-staged，请执行: cd web/frontend && pnpm install')
}

if (errors.length > 0) {
  console.error('Git pre-commit hook 未正确启用:\n')
  for (const error of errors) {
    console.error(`- ${error}`)
  }
  console.error('\n启用后，提交 staged 的 .vue/.ts 文件会自动跑 Prettier + ESLint。')
  process.exit(1)
}

console.log('Git pre-commit hook 已就绪（husky + lint-staged）。')
