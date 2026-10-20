#!/usr/bin/env node
// Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
/**
 * bde-patrol.ts
 * 
 * Boot Disk Encryption (BDE) integrity patrol.
 * Monitors bootloader, kernel, and critical config hashes.
 * Logs tamper events to /var/log/bde/ and optionally alerts.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

const BDE_LOG_DIR = '/var/log/bde';
const BASELINE_FILE = '/etc/zen/bde-baseline.json';
const PATROL_INTERVAL_MS = 15 * 60 * 1000; // 15 minutes

interface HashRecord {
  path: string;
  hash: string;
  algo: string;
  size: number;
  mtime: number;
}

interface Baseline {
  created: string;
  records: HashRecord[];
}

function sha256(filePath: string): string {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function statSize(filePath: string): number {
  try {
    return fs.statSync(filePath).size;
  } catch {
    return 0;
  }
}

function statMtime(filePath: string): number {
  try {
    return fs.statSync(filePath).mtimeMs;
  } catch {
    return 0;
  }
}

function ensureDir(dir: string): void {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  }
}

function log(msg: string): void {
  ensureDir(BDE_LOG_DIR);
  const ts = new Date().toISOString();
  fs.appendFileSync(path.join(BDE_LOG_DIR, 'bde-patrol.log'), `[${ts}] ${msg}\n`);
}

function computeRecord(filePath: string): HashRecord | null {
  try {
    return {
      path: filePath,
      hash: sha256(filePath),
      algo: 'sha256',
      size: statSize(filePath),
      mtime: statMtime(filePath),
    };
  } catch (e) {
    log(`ERROR: failed to hash ${filePath}: ${(e as Error).message}`);
    return null;
  }
}

const CRITICAL_PATHS = [
  '/boot/EFI/BOOT/BOOTX64.EFI',
  '/boot/EFI/BOOT/grubx64.efi',
  '/boot/grub/grub.cfg',
  '/boot/grub/i386-pc/core.img',
  '/boot/vmlinuz-linux',
  '/boot/initramfs-linux.img',
  '/boot/initramfs-linux-fallback.img',
  '/etc/fstab',
  '/etc/crypttab',
  '/etc/systemd/system',
  '/etc/shadow',
  '/etc/passwd',
  '/usr/lib/systemd/systemd',
  '/usr/local/bin/zen-guard',
];

function computeBaseline(): Baseline {
  const records: HashRecord[] = [];
  for (const p of CRITICAL_PATHS) {
    if (fs.existsSync(p)) {
      const rec = computeRecord(p);
      if (rec) records.push(rec);
    }
  }
  return {
    created: new Date().toISOString(),
    records,
  };
}

function loadBaseline(): Baseline | null {
  if (!fs.existsSync(BASELINE_FILE)) return null;
  try {
    return JSON.parse(fs.readFileSync(BASELINE_FILE, 'utf8'));
  } catch {
    return null;
  }
}

function saveBaseline(b: Baseline): void {
  ensureDir(path.dirname(BASELINE_FILE));
  fs.writeFileSync(BASELINE_FILE, JSON.stringify(b, null, 2));
  fs.chmodSync(BASELINE_FILE, 0o600);
}

function verifyIntegrity(): { ok: boolean; violations: string[] } {
  const baseline = loadBaseline();
  if (!baseline) {
    log('No baseline found. Computing and saving initial baseline.');
    const b = computeBaseline();
    saveBaseline(b);
    return { ok: true, violations: ['initial_baseline_created'] };
  }

  const violations: string[] = [];
  for (const rec of baseline.records) {
    if (!fs.existsSync(rec.path)) {
      violations.push(`MISSING: ${rec.path}`);
      continue;
    }
    const current = computeRecord(rec.path);
    if (!current) {
      violations.push(`UNREADABLE: ${rec.path}`);
      continue;
    }
    if (current.hash !== rec.hash) {
      violations.push(`HASH_MISMATCH: ${rec.path} expected=${rec.hash} actual=${current.hash}`);
    }
  }

  return { ok: violations.length === 0, violations };
}

function runPatrol(): void {
  log('Starting BDE integrity patrol...');
  const result = verifyIntegrity();
  if (!result.ok) {
    for (const v of result.violations) {
      log(`TAMPER ALERT: ${v}`);
      console.error(`[bde-patrol] TAMPER: ${v}`);
    }
    // Optional: alert via webhook, email, or systemd notification
  } else {
    log('Patrol complete: integrity OK');
    console.log('[bde-patrol] Integrity OK');
  }
}

// CLI
const args = process.argv.slice(2);
const cmd = args[0] || 'run';

switch (cmd) {
  case 'run':
    runPatrol();
    if (args.includes('--loop')) {
      setInterval(runPatrol, PATROL_INTERVAL_MS);
      log(`Entering patrol loop (every ${PATROL_INTERVAL_MS}ms)`);
    }
    break;
  case 'baseline':
    const b = computeBaseline();
    saveBaseline(b);
    log(`Baseline saved with ${b.records.length} records`);
    console.log(`[bde-patrol] Baseline saved: ${b.records.length} files`);
    break;
  case 'verify':
    const r = verifyIntegrity();
    if (!r.ok) {
      for (const v of r.violations) console.error(`[bde-patrol] ${v}`);
      process.exit(1);
    }
    console.log('[bde-patrol] Integrity OK');
    break;
  default:
    console.log(`
bde-patrol.ts
Usage:
  node bde-patrol.ts run [--loop]
  node bde-patrol.ts baseline
  node bde-patrol.ts verify
    `);
}
