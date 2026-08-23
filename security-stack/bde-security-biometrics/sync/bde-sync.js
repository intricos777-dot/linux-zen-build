#!/usr/bin/env node
/**
 * BDE Sync Daemon
 * Unix-domain socket server for patrol ↔ wrapper communication.
 * Commands:
 *   GET  /            -> status
 *   POST /register    -> {name, command, restart_cmd?}
 *   POST /alert       -> {service, level, message}
 *   POST /fix         -> {service, action}
 *   POST /webpatrol/start -> start hourly web patrol
 *   POST /webpatrol/stop  -> stop hourly web patrol
 *   POST /webpatrol/run   -> run immediate patrol
 */
const http = require('http');
const net = require('net');
const os = require('os');
const fs = require('fs');
const path = require('path');

const SOCKET = '/var/run/bde-sync.sock';
const PORT = 4124;
const WEBPATROL_JS = path.join(__dirname, '..', 'web-patrol', 'scripts', 'bde-webpatrol.js');
let webPatrolProc = null;
let webPatrolTimer = null;

const registry = new Map();
const alerts = [];
const MAX_ALERTS = 200;

function json(status, obj) {
  return { statusCode: status, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) };
}

function audit(ev, data) {
  const logPath = path.join(os.homedir(), '.hermes', 'logs', 'bde-sync-audit.log');
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  const line = `${new Date().toISOString()} ${ev} ${JSON.stringify(data)}\n`;
  fs.appendFileSync(logPath, line, 'utf8');
}

function health() {
  return {
    status: 'ok',
    socket: SOCKET,
    port: PORT,
    registered: registry.size,
    alerts: alerts.length,
    services: Array.from(registry.values()).map(r => ({ name: r.name, command: r.command, lastSeen: r.lastSeen }))
  };
}

function handle(req, res) {
  let body = '';
  req.on('data', d => body += d);
  req.on('end', () => {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const method = req.method;
    let payload = {};
    try { if (body) payload = JSON.parse(body); } catch {}

    if (method === 'GET' && url.pathname === '/') {
      audit('status', {});
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify(health()));
    }

    if (method === 'POST' && url.pathname === '/register') {
      const { name, command, restart_cmd } = payload;
      if (!name || !command) {
        res.writeHead(400);
        return res.end(JSON.stringify({ error: 'name and command required' }));
      }
      const entry = { name, command, restart_cmd: restart_cmd || '', registeredAt: Date.now(), lastSeen: Date.now() };
      registry.set(name, entry);
      audit('register', entry);
      res.writeHead(200);
      return res.end(JSON.stringify({ ok: true, service: entry }));
    }

    if (method === 'POST' && url.pathname === '/alert') {
      const { service, level = 'warn', message } = payload;
      const item = { service, level, message, at: Date.now() };
      alerts.push(item);
      if (alerts.length > MAX_ALERTS) alerts.shift();
      audit('alert', item);
      res.writeHead(200);
      return res.end(JSON.stringify({ ok: true, queued: true }));
    }

    if (method === 'POST' && url.pathname === '/fix') {
      const { service, action } = payload;
      const entry = registry.get(service);
      if (!entry) {
        res.writeHead(404);
        return res.end(JSON.stringify({ error: 'service not registered' }));
      }
      audit('fix', { service, action });
      // Dispatch best-effort restart or custom action
      const cmd = action === 'restart' ? entry.restart_cmd : action;
      if (!cmd) {
        res.writeHead(400);
        return res.end(JSON.stringify({ error: 'no restart_cmd registered and no action provided' }));
      }
      const { exec } = require('child_process');
      exec(cmd, { timeout: 120000 }, (err, stdout, stderr) => {
        const out = { service, action, exit: err ? 1 : 0, stdout: stdout ? stdout.slice(-400) : '', stderr: stderr ? stderr.slice(-400) : '' };
        audit('fix_result', out);
        res.writeHead(200);
        res.end(JSON.stringify(out));
      });
      return;
    }

    if (method === 'POST' && url.pathname === '/webpatrol/start') {
      if (webPatrolProc) {
        res.writeHead(200);
        return res.end(JSON.stringify({ ok: true, already_running: true }));
      }
      try {
        webPatrolProc = require('child_process').fork(WEBPATROL_JS, { silent: false });
        webPatrolProc.on('exit', (code) => {
          audit('webpatrol_exit', { code });
          webPatrolProc = null;
        });
        audit('webpatrol_started', { pid: webPatrolProc.pid });
        res.writeHead(200);
        res.end(JSON.stringify({ ok: true, pid: webPatrolProc.pid }));
      } catch (e) {
        res.writeHead(500);
        res.end(JSON.stringify({ error: e.message }));
      }
      return;
    }

    if (method === 'POST' && url.pathname === '/webpatrol/stop') {
      if (webPatrolProc) {
        webPatrolProc.kill('SIGTERM');
        webPatrolProc = null;
        audit('webpatrol_stopped', {});
      }
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, stopped: true }));
      return;
    }

    if (method === 'POST' && url.pathname === '/webpatrol/run') {
      if (!webPatrolProc) {
        webPatrolProc = require('child_process').fork(WEBPATROL_JS, { silent: false });
        webPatrolProc.on('exit', (code) => {
          audit('webpatrol_exit', { code });
          webPatrolProc = null;
        });
      }
      // Trigger immediate patrol via HTTP
      try {
        new Promise((resolve, reject) => {
          const req = http.request({
            host: '127.0.0.1', port: PORT, path: '/patrol', method: 'POST',
            headers: { 'Content-Type': 'application/json' }, timeout: 30000
          }, (res) => {
            let data = '';
            res.on('data', d => data += d);
            res.on('end', () => resolve(JSON.parse(data)));
          });
          req.on('error', reject);
          req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
          req.write(JSON.stringify({}));
          req.end();
        }).then(result => {
          res.writeHead(200);
          res.end(JSON.stringify({ ok: true, patrol: result }));
        }).catch(e => {
          res.writeHead(500);
          res.end(JSON.stringify({ error: e.message }));
        });
      } catch (e) {
        res.writeHead(500);
        res.end(JSON.stringify({ error: e.message }));
      }
      return;
    }

    if (method === 'POST' && url.pathname === '/webpatrol/package') {
      let payload = {};
      try { if (body) payload = JSON.parse(body); } catch {}
      const { startDate, endDate, caseId } = payload;
      // Delegate to builder
      const { spawn } = require('child_process');
      const builder = spawn('node', [
        path.join(__dirname, '..', 'web-patrol', 'scripts', 'build-lawsuit-package.js'),
        '--from', startDate || '', '--to', endDate || '', '--case', caseId || `case-${Date.now()}`
      ], { stdio: 'pipe' });
      let out = '';
      builder.stdout.on('data', d => out += d);
      builder.stderr.on('data', d => console.error('pkg err:', d.toString()));
      builder.on('close', (code) => {
        audit('lawsuit_package_build', { code, output: out.slice(-1000) });
        res.writeHead(code === 0 ? 200 : 500);
        res.end(JSON.stringify({ ok: code === 0, output: out }));
      });
      return;
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'not found' }));
  });
}

async function main() {
  if (fs.existsSync(SOCKET)) fs.unlinkSync(SOCKET);

  const tcp = http.createServer(handle);
  tcp.listen(PORT, '127.0.0.1', () => {
    console.log(`BDE sync TCP on 127.0.0.1:${PORT}`);
  });

  const unix = net.createServer((socket) => {
    const req = http.IncomingMessage(socket);
    const res = new http.ServerResponse(req);
    handle(req, res);
  });
  unix.listen(SOCKET, () => {
    fs.chmodSync(SOCKET, 0o777);
    console.log(`BDE sync Unix socket at ${SOCKET}`);
  });

  const shutdown = () => {
    try { tcp.close(); } catch {}
    try { unix.close(); } catch {}
    try { if (fs.existsSync(SOCKET)) fs.unlinkSync(SOCKET); } catch {}
    process.exit(0);
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((e) => {
  console.error('bde-sync fatal:', e);
  process.exit(1);
});
