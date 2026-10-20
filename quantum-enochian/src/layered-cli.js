#!/usr/bin/env node
// Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { seal, unseal, LAYER_NAMES, layerPassphrase, derivePersonalLayerKey, status } from './layered-enochian.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const HOME = process.env.HOME || process.env.USERPROFILE || '.';
const LAYERED_DIR = resolve(HOME, '.quantum-enochian-layered');
const PERSONAL_KEYS = resolve(LAYERED_DIR, 'keys');
const PERSONAL_SEALS = resolve(LAYERED_DIR, 'sealed');

if (!existsSync(PERSONAL_KEYS)) mkdirSync(PERSONAL_KEYS, { recursive: true });
if (!existsSync(PERSONAL_SEALS)) mkdirSync(PERSONAL_SEALS, { recursive: true });

function personalKeyPath(layerIndex, name) {
  return resolve(PERSONAL_KEYS, `layer-${String(layerIndex).padStart(2,'0')}-${name}.key.json`);
}

function cmdStatus() {
  const s = status();
  console.log('Quantum Enochian Layered Format');
  console.log('================================');
  for (let i = 0; i < s.layers.length; i++) {
    const element = s.elements[i] || 'unknown';
    const p = layerPassphrase(i, '<USER_SECRET>', '<CONTEXT>').substring(0, 18) + '...';
    console.log(`  Layer ${i + 1}: ${s.layers[i]} (${element}) — passphrase=${p}`);
  }
}

function cmdSeal(opts) {
  const input = opts.input || opts._?.[0];
  const userSecret = opts.secret || opts.userSecret;
  const context = opts.context || '';
  const name = opts.name || `seal-${Date.now()}`;
  if (!input || !userSecret) {
    console.error('Usage: layered seal --input <text|file> --secret <your-secret> [--context <ctx>] [--name <name>]');
    process.exit(1);
  }
  const plaintext = existsSync(resolve(input)) ? readFileSync(resolve(input), 'utf8') : input;
  const sealed = seal(plaintext, userSecret, context);
  const outPath = resolve(PERSONAL_SEALS, `${name}.sealed`);
  writeFileSync(outPath, sealed);
  console.log(`Sealed across ${LAYER_NAMES.length} layers -> ${outPath}`);
}

function cmdUnseal(opts) {
  const input = opts.input || opts._?.[0];
  const userSecret = opts.secret || opts.userSecret;
  const context = opts.context || '';
  if (!input || !userSecret) {
    console.error('Usage: layered unseal --input <sealed-file|base64> --secret <your-secret> [--context <ctx>]');
    process.exit(1);
  }
  const blob = existsSync(resolve(input)) ? readFileSync(resolve(input), 'utf8') : input;
  const recovered = unseal(blob, userSecret, context);
  console.log(recovered);
}

function cmdKeygen(opts) {
  const layerIndex = parseInt(opts.layer) || 0;
  const name = opts.name || 'default';
  const entropyFile = opts.entropy || '';
  const personalSecret = opts.secret || opts.userSecret || name;
  const key = derivePersonalLayerKey(layerIndex, personalSecret, entropyFile);
  const payload = JSON.stringify({ layer: layerIndex, name, key, created: new Date().toISOString() }, null, 2);
  const path = personalKeyPath(layerIndex, name);
  writeFileSync(path, payload);
  console.log(`Personal layer ${layerIndex + 1} (${LAYER_NAMES[layerIndex]}) key written to ${path}`);
}

function main() {
  const args = process.argv.slice(2);
  const cmd = args[0];
  const opts = {};
  for (let i = 1; i < args.length; i++) {
    if (args[i].startsWith('--')) {
      const key = args[i].slice(2);
      const val = args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : true;
      opts[key] = val;
      if (val !== true) i++;
    }
  }
  switch (cmd) {
    case 'status': cmdStatus(); break;
    case 'seal': cmdSeal(opts); break;
    case 'unseal': cmdUnseal(opts); break;
    case 'keygen': cmdKeygen(opts); break;
    default:
      console.log('Quantum Enochian Layered Encryption');
      console.log('');
      console.log('Commands:');
      console.log('  layered status');
      console.log('  layered seal --input <text|file> --secret <your-secret> [--context ctx] [--name name]');
      console.log('  layered unseal --input <file|base64> --secret <your-secret> [--context ctx]');
      console.log(`  layered keygen --layer <0-${LAYER_NAMES.length - 1}> [--name label] [--secret personal-secret] [--entropy file]`);
  }
}
main();
