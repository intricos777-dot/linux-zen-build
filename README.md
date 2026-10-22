<!-- Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work -->
# linux-zen-build

Unified rebuild of the zen security stack, CPU miners, and the 21-layer
quantum-enochian encryption system. Private by design.

## Contents
- `miners/` — true solo mining: BTC/LTC/DOGE on CPU, RVN on GPU, each against
  its own local full node. No pool. See `miners/README.md`
- `quantum-enochian/` — 21-layer layered encryption engine (3 triads of 7),
  binary-safe unwrap fix, full test suite
- `security-stack/` — deploy scripts: lin-antimalware (linAV), lin-antimalware-tools,
  local-emergency-patrol, bde-security-biometrics PAM daemon, rfkill-lock
  (wifi killswitch hardening)
- `zen-suite/` — buildable PKGBUILD for zen-core tooling
- `snapshots/` — pre/post btrfs snapshot helpers
- `docs/BUGFIXES.md` — every fix applied during this rebuild

## Rebuild procedure
```bash
sudo -v                      # or enable passwordless sudo temporarily
bash snapshots/pre-snapshot.sh
bash rebuild.sh
bash snapshots/post-snapshot.sh
```

## Wallets

As recorded by the owner, carried into `miners/solo/configs/` unchanged:

- BTC: `33oBrFCtn7SvqULsERymwtwmM8mXSrgcd9` — verified valid (P2SH)
- LTC: `MQ3qudKtDzSmwg7tHUV7JZTXizLYBtzffj` — verified valid (P2SH)
- DOGE: `Dai6AHB6D4M152PWjnHNFF8v` — **INVALID**, bad checksum and a Bitcoin
  version byte. Preserved as recorded; the DOGE service refuses to start until
  it is replaced.
- RVN: none on record. Placeholder only; an address will not be invented.

The pool endpoints previously listed here (solo.ckpool.org, ltc.viabtc.io,
scrypt.mine.zpool.ca) are gone. Mining is now solo against local daemons:
`solo_bridge.py` translates stratum to `getblocktemplate` over local RPC.

Not supported, and deliberately absent: GPU Bitcoin mining (SHA-256 has been
ASIC-only since ~2013) and merged LTC+DOGE mining (Dogecoin removed auxpow in
2014). See `miners/README.md`.

## Scan status
Full 84-repo GitHub audit performed pre-rebuild: no keyloggers, backdoors,
reverse shells, webhook exfiltration, or committed credentials found.
