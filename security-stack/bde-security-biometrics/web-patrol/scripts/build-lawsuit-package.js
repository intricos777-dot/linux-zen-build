#!/usr/bin/env node
/**
 * BDE Web Patrol - Lawsuit Package Builder
 * Bundles archived findings into a tamper-evident legal package.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { exec } = require('child_process');
const { promisify } = require('util');
const execAsync = promisify(exec);

const ARCHIVE_DIR = path.join(os.homedir(), '.bde', 'webpatrol', 'archive');
const PACKAGE_DIR = path.join(os.homedir(), '.bde', 'webpatrol', 'packages');
const LOG_DIR = path.join(os.homedir(), '.hermes', 'logs');

function sha256(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function audit(ev, data) {
  const logPath = path.join(LOG_DIR, 'bde-webpatrol.log');
  const line = `${new Date().toISOString()} ${ev} ${JSON.stringify(data)}\n`;
  fs.appendFileSync(logPath, line, 'utf8');
}

function findFindings(startDate, endDate) {
  const findings = [];
  if (!fs.existsSync(ARCHIVE_DIR)) return findings;

  const years = fs.readdirSync(ARCHIVE_DIR).filter(f => !isNaN(f));
  for (const year of years) {
    const months = fs.readdirSync(path.join(ARCHIVE_DIR, year)).filter(f => !isNaN(f));
    for (const month of months) {
      const days = fs.readdirSync(path.join(ARCHIVE_DIR, year, month)).filter(f => !isNaN(f));
      for (const day of days) {
        const dir = path.join(ARCHIVE_DIR, year, month, day);
        const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));
        for (const file of files) {
          const filepath = path.join(dir, file);
          const stat = fs.statSync(filepath);
          const mtime = stat.mtime.toISOString();
          if (startDate && mtime < startDate) continue;
          if (endDate && mtime > endDate) continue;

          try {
            const content = fs.readFileSync(filepath, 'utf8');
            const finding = JSON.parse(content);
            finding._archive_file = filepath;
            finding._archive_hash = sha256(content);
            findings.push(finding);
          } catch {}
        }
      }
    }
  }

  // Sort by detection time
  findings.sort((a, b) => new Date(a.detectedAt) - new Date(b.detectedAt));
  return findings;
}

function buildPackage(startDate, endDate, caseId) {
  const findings = findFindings(startDate, endDate);
  if (findings.length === 0) {
    console.error('No findings found for the given date range.');
    process.exit(1);
  }

  fs.mkdirSync(PACKAGE_DIR, { recursive: true });
  const pkgId = caseId || `case-${Date.now()}`;
  const pkgDir = path.join(PACKAGE_DIR, pkgId);
  fs.mkdirSync(pkgDir, { recursive: true });

  // Write findings
  const findingsFile = path.join(pkgDir, 'findings.json');
  const findingsContent = JSON.stringify(findings, null, 2);
  fs.writeFileSync(findingsFile, findingsContent, 'utf8');
  fs.chmodSync(findingsFile, 0o600);

  // Write manifest
  const manifest = {
    packageId: pkgId,
    generatedAt: new Date().toISOString(),
    generatedBy: os.userInfo().username,
    hostname: os.hostname(),
    findingCount: findings.length,
    dateRange: { start: startDate || 'earliest', end: endDate || 'latest' },
    chainOfCustody: {
      collector: 'bde-webpatrol',
      method: 'automated_hourly_patrol',
      sources: findings.map(f => f._archive_file),
      totalHash: sha256(findingsContent),
      verification: 'sha256'
    },
    summary: {
      domains: [...new Set(findings.map(f => f.domain))],
      signalCounts: {}
    }
  };

  // Count signals
  findings.forEach(f => {
    (f.signals || []).forEach(s => {
      manifest.summary.signalCounts[s] = (manifest.summary.signalCounts[s] || 0) + 1;
    });
  });

  const manifestFile = path.join(pkgDir, 'manifest.json');
  fs.writeFileSync(manifestFile, JSON.stringify(manifest, null, 2), 'utf8');
  fs.chmodSync(manifestFile, 0o600);

  // Create tarball
  const tarball = path.join(PACKAGE_DIR, `${pkgId}.tar.gz`);
  try {
    execAsync(`tar -czf "${tarball}" -C "${PACKAGE_DIR}" "${pkgId}"`, { timeout: 30000 });
    audit('lawsuit_package', { package: pkgId, file: tarball, findings: findings.length });
    console.log(`[lawsuit-pkg] Package created: ${tarball}`);
    console.log(`[lawsuit-pkg] Findings: ${findings.length}`);
    console.log(`[lawsuit-pkg] Manifest: ${manifestFile}`);
    console.log(`[lawsuit-pkg] Total SHA256: ${manifest.chainOfCustody.totalHash}`);
  } catch (e) {
    console.error('Failed to create tarball:', e.message);
    console.log(`[lawsuit-pkg] Files available at: ${pkgDir}`);
  }
}

function main() {
  const args = process.argv.slice(2);
  let startDate, endDate, caseId;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--from' && args[i+1]) { startDate = args[++i]; }
    else if (args[i] === '--to' && args[i+1]) { endDate = args[++i]; }
    else if (args[i] === '--case' && args[i+1]) { caseId = args[++i]; }
  }

  buildPackage(startDate, endDate, caseId);
}

main();
