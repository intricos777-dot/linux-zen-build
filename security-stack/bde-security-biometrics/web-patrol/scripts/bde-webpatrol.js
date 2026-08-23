#!/usr/bin/env node
/**
 * BDE Web Patrol Daemon
 * Hourly web patrol to detect AI-assisted tracking/competition.
 * Archives evidence for potential legal action.
 */

const http = require('http');
const net = require('net');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { exec } = require('child_process');
const { promisify } = require('util');
const execAsync = promisify(exec);

const SOCKET = path.join(os.homedir(), '.bde', 'webpatrol', 'bde-webpatrol.sock');
const PORT = 4125;
const ARCHIVE_DIR = path.join(os.homedir(), '.bde', 'webpatrol', 'archive');
const LOG_DIR = path.join(os.homedir(), '.hermes', 'logs');
const PATROL_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

// Keywords indicating AI-assisted competitive tracking
const AI_TRACKING_PATTERNS = [
  'gpt', 'claude', 'gemini', 'copilot', 'llama', 'midjourney', 'dall-e',
  'openai', 'anthropic', 'langchain', 'vector database', 'embedding',
  'scraper', 'crawler', 'bot', 'automated', 'api key', 'api_token',
  'webhook', 'real-time', 'live feed', 'data enrichment', 'osint',
  'competitive intelligence', 'market research', 'price monitoring'
];

const COMPETITOR_DOMAINS = [
  // User can extend this list via config/webpatrol.json
];

fs.mkdirSync(ARCHIVE_DIR, { recursive: true });
fs.mkdirSync(LOG_DIR, { recursive: true });

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

function sha256(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function audit(ev, data) {
  const logPath = path.join(LOG_DIR, 'bde-webpatrol.log');
  const line = `${new Date().toISOString()} ${ev} ${JSON.stringify(data)}\n`;
  fs.appendFileSync(logPath, line, 'utf8');
}

// Evidence archive format:
// archive/<year>/<month>/<day>/<timestamp>_<sha256>.json
function archiveEvidence(finding) {
  const d = new Date(finding.detectedAt || Date.now());
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const dir = path.join(ARCHIVE_DIR, String(year), month, day);
  fs.mkdirSync(dir, { recursive: true });

  const payload = JSON.stringify(finding, null, 2);
  const hash = sha256(payload);
  const filename = `${timestamp()}_${hash.slice(0, 16)}.json`;
  const filepath = path.join(dir, filename);

  fs.writeFileSync(filepath, payload, 'utf8');
  fs.chmodSync(filepath, 0o600);

  audit('archive', { file: filepath, hash, size: payload.length });
  return filepath;
}

function detectAISignals(text) {
  if (!text) return [];
  const lower = text.toLowerCase();
  const hits = [];
  for (const pattern of AI_TRACKING_PATTERNS) {
    if (lower.includes(pattern)) {
      hits.push(pattern);
    }
  }
  return hits;
}

async function fetchURL(url, timeout = 10000) {
  // Try wget or curl as evidence fetcher
  try {
    const { stdout } = await execAsync(
      `curl -sL --max-time ${Math.floor(timeout/1000)} -A "Mozilla/5.0 (compatible; BDE-Patrol/1.0)" "${url}"`,
      { timeout: timeout + 2000 }
    );
    return stdout;
  } catch {
    return null;
  }
}

async function patrolTarget(target) {
  const url = typeof target === 'string' ? target : target.url;
  audit('patrol_start', { url });

  const body = await fetchURL(url);
  if (!body) {
    audit('patrol_fail', { url, reason: 'fetch_failed' });
    return null;
  }

  const signals = detectAISignals(body);
  const finding = {
    url,
    domain: new URL(url).hostname,
    detectedAt: new Date().toISOString(),
    patrolType: 'ai_tracking_competitor',
    signals,
    snippet: body.slice(0, 4000),
    userAgent: 'BDE-Patrol/1.0 (+https://github.com/intricos777-dot/bde-security-biometrics)',
    chainOfCustody: {
      collectedBy: 'bde-webpatrol',
      collectedAt: new Date().toISOString(),
      hash: sha256(body),
      method: 'active_web_patrol',
      jurisdiction: 'user_controlled'
    }
  };

  if (signals.length > 0) {
    const filepath = archiveEvidence(finding);
    audit('patrol_hit', { url, signals, file: filepath });
    return { ...finding, archivedAt: filepath };
  }

  audit('patrol_clean', { url });
  return null;
}

async function runPatrolCycle() {
  audit('cycle_start', { targets: COMPETITOR_DOMAINS.length });
  const hits = [];

  for (const target of COMPETITOR_DOMAINS) {
    try {
      const finding = await patrolTarget(target);
      if (finding) hits.push(finding);
    } catch (e) {
      audit('patrol_error', { url: target, error: e.message });
    }
  }

  audit('cycle_end', { hits: hits.length });
  return hits;
}

// HTTP API for integration with bde-sync
function handleRequest(req, res) {
  let body = '';
  req.on('data', d => body += d);
  req.on('end', () => {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const method = req.method;

    if (method === 'GET' && url.pathname === '/') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({
        status: 'ok',
        socket: SOCKET,
        port: PORT,
        archive: ARCHIVE_DIR,
        targets: COMPETITOR_DOMAINS.length,
        interval: PATROL_INTERVAL_MS
      }));
    }

    if (method === 'POST' && url.pathname === '/patrol') {
      let payload = {};
      try { if (body) payload = JSON.parse(body); } catch {}
      const targets = payload.targets || COMPETITOR_DOMAINS;
      audit('manual_patrol', { count: targets.length });
      Promise.all(targets.map(t => patrolTarget(t).catch(() => null)))
        .then(results => {
          const hits = results.filter(Boolean);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, hits: hits.length, findings: hits }));
        })
        .catch(err => {
          res.writeHead(500);
          res.end(JSON.stringify({ error: err.message }));
        });
      return;
    }

    if (method === 'POST' && url.pathname === '/add-target') {
      let payload = {};
      try { if (body) payload = JSON.parse(body); } catch {}
      if (payload.url && !COMPETITOR_DOMAINS.includes(payload.url)) {
        COMPETITOR_DOMAINS.push(payload.url);
        audit('target_added', { url: payload.url });
      }
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, targets: COMPETITOR_DOMAINS }));
      return;
    }

    if (method === 'POST' && url.pathname === '/archive') {
      let payload = {};
      try { if (body) payload = JSON.parse(body); } catch {}
      const filepath = archiveEvidence(payload);
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true, file: filepath }));
      return;
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'not found' }));
  });
}

async function main() {
  if (fs.existsSync(SOCKET)) fs.unlinkSync(SOCKET);
  const sockDir = path.dirname(SOCKET);
  if (!fs.existsSync(sockDir)) fs.mkdirSync(sockDir, { recursive: true });

  // Load config
  const configPath = path.join(__dirname, '..', 'config', 'webpatrol.json');
  try {
    if (fs.existsSync(configPath)) {
      const cfg = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      if (cfg.targets && Array.isArray(cfg.targets)) {
        cfg.targets.forEach(t => { if (!COMPETITOR_DOMAINS.includes(t)) COMPETITOR_DOMAINS.push(t); });
      }
      if (cfg.patterns && Array.isArray(cfg.patterns)) {
        cfg.patterns.forEach(p => { if (!AI_TRACKING_PATTERNS.includes(p)) AI_TRACKING_PATTERNS.push(p); });
      }
    }
  } catch {}

  const tcp = http.createServer(handleRequest);
  tcp.listen(PORT, '127.0.0.1', () => {
    console.log(`BDE web patrol TCP on 127.0.0.1:${PORT}`);
  });

  const unix = net.createServer((socket) => {
    const req = http.IncomingMessage(socket);
    const res = new http.ServerResponse(req);
    handleRequest(req, res);
  });
  unix.listen(SOCKET, () => {
    fs.chmodSync(SOCKET, 0o777);
    console.log(`BDE web patrol Unix socket at ${SOCKET}`);
  });

  // Hourly patrol
  console.log(`BDE web patrol starting. Interval: ${PATROL_INTERVAL_MS/1000}s`);
  console.log(`Targets: ${COMPETITOR_DOMAINS.length}`);
  console.log(`Archive: ${ARCHIVE_DIR}`);

  await runPatrolCycle(); // initial
  setInterval(() => {
    runPatrolCycle().catch(e => console.error('patrol cycle error:', e.message));
  }, PATROL_INTERVAL_MS);

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
  console.error('bde-webpatrol fatal:', e);
  process.exit(1);
});
