#!/usr/bin/env node
// Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
/**
 * BDE Sync Client
 * HTTP client to bde-sync daemon at http://127.0.0.1:4124 or unix:///var/run/bde-sync.sock
 */
const http = require('http');
const net = require('net');

const TCP_HOST = '127.0.0.1';
const TCP_PORT = 4124;
const UNIX_SOCKET = '/var/run/bde-sync.sock';

function request(method, path, payload) {
  return new Promise((resolve, reject) => {
    const body = payload ? JSON.stringify(payload) : '';
    const options = {
      method,
      path,
      headers: { 'Content-Type': 'application/json' },
      timeout: 5000
    };

    // Prefer TCP, fallback to unix socket
    const req = http.request({ ...options, host: TCP_HOST, port: TCP_PORT }, (res) => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, body: data });
        }
      });
    });

    req.on('error', () => {
      // Fallback to unix socket
      const client = net.createConnection({ path: UNIX_SOCKET });
      client.write(`${method} ${path} HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: ${Buffer.byteLength(body)}\r\nConnection: close\r\n\r\n${body}`);
      let buf = '';
      client.on('data', d => buf += d);
      client.on('end', () => {
        const match = buf.match(/HTTP\/\d\.\d (\d+)/);
        const status = match ? parseInt(match[1]) : 0;
        const bodyStart = buf.indexOf('\r\n\r\n');
        const bodyStr = bodyStart >= 0 ? buf.slice(bodyStart + 4) : '';
        try {
          resolve({ status, body: JSON.parse(bodyStr) });
        } catch {
          resolve({ status, body: bodyStr });
        }
      });
      client.on('error', reject);
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error('timeout'));
    });

    if (body) req.write(body);
    req.end();
  });
}

async function main() {
  const cmd = process.argv[2];
  const args = process.argv.slice(3);
  let result;

  if (cmd === 'register') {
    const [name, command, restart_cmd] = args;
    result = await request('POST', '/register', { name, command, restart_cmd });
  } else if (cmd === 'alert') {
    const [service, level, ...msgParts] = args;
    result = await request('POST', '/alert', { service, level: level || 'warn', message: msgParts.join(' ') });
  } else if (cmd === 'fix') {
    const [service, action] = args;
    result = await request('POST', '/fix', { service, action });
  } else if (cmd === 'status') {
    result = await request('GET', '/');
  } else {
    console.error('Usage: sync-client <register|alert|fix|status> [args...]');
    process.exit(2);
  }

  console.log(JSON.stringify(result, null, 2));
  process.exit(result.status >= 400 ? 1 : 0);
}

main().catch((e) => {
  console.error('sync-client error:', e.message);
  process.exit(1);
});
