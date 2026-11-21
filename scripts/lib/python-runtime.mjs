import fs from 'node:fs'
import path from 'node:path'

export function shellQuoteCommand(value) {
  return `"${String(value).replace(/"/g, '\\"')}"`
}

export function bashQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`
}

export function resolvePythonExecutable(cwd, options = {}) {
  const existsSync = options.existsSync ?? fs.existsSync
  const platform = options.platform ?? process.platform
  const candidates = [
    path.join(cwd, '.venv', 'bin', 'python'),
    path.join(cwd, 'venv', 'bin', 'python'),
    path.join(cwd, '.venv', 'Scripts', 'python.exe'),
    path.join(cwd, 'venv', 'Scripts', 'python.exe'),
  ]

  const venvPython = candidates.find((candidate) => existsSync(candidate))
  if (venvPython) {
    return venvPython
  }

  return platform === 'win32' ? 'python' : 'python3'
}

export function replaceLeadingPythonCommand(command, pythonExecutable) {
  if (!/^(python|python3)(\s|$)/.test(command)) {
    return command
  }
  return command.replace(/^(python|python3)(?=\s|$)/, shellQuoteCommand(pythonExecutable))
}

export function replaceLeadingPythonCommandForBash(command, pythonExecutable) {
  if (!/^(python|python3)(\s|$)/.test(command)) {
    return command
  }
  return command.replace(/^(python|python3)(?=\s|$)/, bashQuote(pythonExecutable))
}

export function isLinuxPythonExecutable(pythonExecutable) {
  return /[\\/]bin[\\/]python$/.test(pythonExecutable)
}

export function toPosixRelativePath(from, to) {
  return path.relative(from, to).replace(/\\/g, '/')
}
