#!/usr/bin/env node

import http from "node:http";
import net from "node:net";
import { URL } from "node:url";

const listenHost = process.env.CF_LOCAL_PROXY_HOST ?? "127.0.0.1";
const listenPort = Number.parseInt(process.env.CF_LOCAL_PROXY_PORT ?? "15173", 10);
const targetUrl = new URL(process.env.CF_LOCAL_PROXY_TARGET ?? "http://platform.example.invalid:5173");

if (targetUrl.protocol !== "http:") {
  throw new Error(`Only http targets are supported, got ${targetUrl.protocol}`);
}

if (!Number.isInteger(listenPort) || listenPort <= 0 || listenPort > 65535) {
  throw new Error(`Invalid CF_LOCAL_PROXY_PORT: ${process.env.CF_LOCAL_PROXY_PORT}`);
}

function targetPath(reqUrl) {
  return new URL(reqUrl ?? "/", targetUrl).pathname + new URL(reqUrl ?? "/", targetUrl).search;
}

const server = http.createServer((req, res) => {
  const headers = {
    ...req.headers,
    host: targetUrl.host,
  };

  const proxyReq = http.request(
    {
      host: targetUrl.hostname,
      port: targetUrl.port || 80,
      path: targetPath(req.url),
      method: req.method,
      headers,
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode ?? 502, proxyRes.headers);
      proxyRes.pipe(res);
    },
  );

  proxyReq.on("error", (error) => {
    res.writeHead(502, { "content-type": "text/plain; charset=utf-8" });
    res.end(`Local proxy failed to reach ${targetUrl.href}: ${error.message}\n`);
  });

  req.pipe(proxyReq);
});

server.on("upgrade", (req, socket, head) => {
  const upstream = net.connect(Number.parseInt(targetUrl.port || "80", 10), targetUrl.hostname, () => {
    const headers = Object.entries({ ...req.headers, host: targetUrl.host })
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`)
      .join("\r\n");

    upstream.write(`${req.method} ${targetPath(req.url)} HTTP/${req.httpVersion}\r\n${headers}\r\n\r\n`);
    if (head.length > 0) {
      upstream.write(head);
    }
    upstream.pipe(socket);
    socket.pipe(upstream);
  });

  upstream.on("error", () => socket.destroy());
});

server.listen(listenPort, listenHost, () => {
  console.log(`cloudflare-local-proxy listening on http://${listenHost}:${listenPort}`);
  console.log(`forwarding to ${targetUrl.href}`);
});

