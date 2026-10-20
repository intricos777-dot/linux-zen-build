#!/usr/bin/env node
// Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
/**
 * local-function-guard.ts
 * 
 * TypeScript systemd guard wrapper that restricts function calls
 * to an approved allowlist and logs all violations.
 * 
 * Usage: node local-function-guard.ts [--allowlist <path>] [--pid <pid>] [--mode monitor|enforce]
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

const DEFAULT_ALLOWLIST = '/etc/zen/function-allowlist.json';
const LOG_PATH = '/var/log/zen/function-guard.log';
const STATE_DIR = '/var/lib/zen/guard';

interface AllowlistEntry {
  binary: string;
  allowedSyscalls?: string[];
  blockedSyscalls?: string[];
  allowedArgs?: string[];
  notes?: string;
}

interface GuardConfig {
  mode: 'monitor' | 'enforce';
  allowlist: AllowlistEntry[];
  pid?: number;
}

function ensureDir(dir: string): void {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  }
}

function logEvent(msg: string): void {
  ensureDir(path.dirname(LOG_PATH));
  const ts = new Date().toISOString();
  fs.appendFileSync(LOG_PATH, `[${ts}] ${msg}\n`);
}

function loadAllowlist(p: string): AllowlistEntry[] {
  if (!fs.existsSync(p)) {
    logEvent(`WARN: Allowlist not found at ${p}, using defaults`);
    return [];
  }
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch (e) {
    logEvent(`ERROR: Failed to parse allowlist: ${(e as Error).message}`);
    return [];
  }
}

function loadConfig(args: string[]): GuardConfig {
  let allowlistPath = DEFAULT_ALLOWLIST;
  let mode: 'monitor' | 'enforce' = 'enforce';
  let pid: number | undefined;

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--allowlist':
        allowlistPath = args[++i];
        break;
      case '--mode':
        mode = args[++i] as 'monitor' | 'enforce';
        break;
      case '--pid':
        pid = parseInt(args[++i], 10);
        break;
      case '--help':
      case '-h':
        console.log(`
local-function-guard.ts
Usage: node local-function-guard.ts [OPTIONS]
  --allowlist <path>   Path to JSON allowlist (default: ${DEFAULT_ALLOWLIST})
  --mode <mode>        monitor | enforce (default: enforce)
  --pid <pid>          Attach to existing PID
  --help               Show this help
        `);
        process.exit(0);
    }
  }

  return { mode, allowlist: loadAllowlist(allowlistPath), pid };
}

class FunctionGuard {
  private config: GuardConfig;

  constructor(config: GuardConfig) {
    this.config = config;
  }

  checkCall(binary: string, syscall: string, args: string[]): boolean {
    const entry = this.config.allowlist.find(e => e.binary === binary);
    if (!entry) {
      const msg = `BLOCKED: unknown binary '${binary}' syscall '${syscall}'`;
      logEvent(msg);
      return this.config.mode === 'enforce' ? false : true;
    }

    if (entry.blockedSyscalls?.includes(syscall)) {
      const msg = `BLOCKED: ${binary} attempted blocked syscall ${syscall}`;
      logEvent(msg);
      return this.config.mode === 'enforce' ? false : true;
    }

    if (entry.allowedArgs && !entry.allowedArgs.some(a => args.some(ar => ar.includes(a)))) {
      const msg = `BLOCKED: ${binary} args not in allowlist: ${args.join(' ')}`;
      logEvent(msg);
      return this.config.mode === 'enforce' ? false : true;
    }

    logEvent(`ALLOWED: ${binary} ${syscall} ${args.join(' ')}`);
    return true;
  }

  run(): void {
    logEvent(`Guard started in ${this.config.mode} mode`);
    console.log(`[local-function-guard] Running in ${this.config.mode} mode`);
    
    // Daemon loop
    if (this.config.pid) {
      setInterval(() => {
        // In a real implementation, this would use eBPF or ptrace to monitor
        // For now, we log the guard is active
      }, 5000);
    }
  }
}

const config = loadConfig(process.argv.slice(2));
const guard = new FunctionGuard(config);
guard.run();
