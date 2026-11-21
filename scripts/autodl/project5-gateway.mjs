import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const host = process.env.AUTODL_GATEWAY_HOST || '0.0.0.0'
const port = Number(process.env.AUTODL_GATEWAY_PORT || 6006)
const backendUrl = new URL(process.env.PROJECT5_BACKEND_URL || 'http://127.0.0.1:5800')
const frontendRoot = process.env.PROJECT5_FRONTEND_ROOT || path.resolve('web/frontend/dist')
const indexPath = path.join(frontendRoot, 'index.html')

const contentTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.map', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.jpg', 'image/jpeg'],
  ['.jpeg', 'image/jpeg'],
  ['.svg', 'image/svg+xml'],
  ['.ico', 'image/x-icon'],
  ['.woff', 'font/woff'],
  ['.woff2', 'font/woff2'],
])

function send(res, status, body, headers = {}) {
  res.writeHead(status, headers)
  res.end(body)
}

function safeFilePath(urlPath) {
  const decoded = decodeURIComponent(urlPath)
  const normalized = path.normalize(decoded).replace(/^(\.\.[/\\])+/, '')
  const relative = normalized.replace(/^[/\\]+/, '')
  const candidate = path.join(frontendRoot, relative)
  const root = path.resolve(frontendRoot)
  const resolved = path.resolve(candidate)
  if (resolved !== root && !resolved.startsWith(root + path.sep)) {
    return null
  }
  return resolved
}

function proxyApi(req, res, parsedUrl) {
  const target = new URL(backendUrl)
  if (parsedUrl.pathname === '/api/health') {
    target.pathname = '/health'
  } else {
    target.pathname = parsedUrl.pathname
  }
  target.search = parsedUrl.search

  const headers = { ...req.headers, host: target.host }
  const proxyReq = http.request(
    target,
    {
      method: req.method,
      headers,
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers)
      proxyRes.pipe(res)
    },
  )
  proxyReq.on('error', (error) => {
    send(
      res,
      502,
      JSON.stringify({ error: 'backend unavailable', detail: error.message }),
      { 'content-type': 'application/json; charset=utf-8' },
    )
  })
  req.pipe(proxyReq)
}

function serveStatic(req, res, parsedUrl) {
  const requested = parsedUrl.pathname === '/' ? indexPath : safeFilePath(parsedUrl.pathname)
  if (!requested) {
    send(res, 403, 'Forbidden')
    return
  }

  fs.stat(requested, (statError, stat) => {
    const filePath = !statError && stat.isFile() ? requested : indexPath
    fs.readFile(filePath, (readError, data) => {
      if (readError) {
        send(res, 404, 'Not found')
        return
      }
      const type = contentTypes.get(path.extname(filePath).toLowerCase()) || 'application/octet-stream'
      send(res, 200, data, { 'content-type': type })
    })
  })
}

const server = http.createServer((req, res) => {
  const parsedUrl = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`)
  if (parsedUrl.pathname === '/api' || parsedUrl.pathname.startsWith('/api/')) {
    proxyApi(req, res, parsedUrl)
    return
  }
  serveStatic(req, res, parsedUrl)
})

server.listen(port, host, () => {
  const script = fileURLToPath(import.meta.url)
  console.log(`[llmsafe-autodl] gateway listening on http://${host}:${port}`)
  console.log(`[llmsafe-autodl] frontend root: ${frontendRoot}`)
  console.log(`[llmsafe-autodl] backend: ${backendUrl.href}`)
  console.log(`[llmsafe-autodl] script: ${script}`)
})
