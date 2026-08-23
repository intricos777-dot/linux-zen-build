# linux-zen-build

Unified rebuild of the zen security stack, CPU miners, and the 21-layer
quantum-enochian encryption system. Private by design.

## Contents
- `miners/` — BTC solo (CPU), LTC solo (CPU), DOGE (CPU) + installer
- `quantum-enochian/` — 21-layer layered encryption engine (3 triads of 7),
  binary-safe unwrap fix, full test suite
- `security-stack/` — deploy scripts: lin-antimalware (linAV), lin-antimalware-tools,
  local-emergency-patrol, bde-security-biometrics PAM daemon
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

## Wallets (as configured by owner)
- BTC solo: `33oBrFCtn7SvqULsERymwtwmM8mXSrgcd9` @ solo.ckpool.org
- LTC solo: `MQ3qudKtDzSmwg7tHUV7JZTXizLYBtzffj` @ ltc.viabtc.io
- DOGE:     `Dai6AHB6D4M152PWjnHNFF8v` @ scrypt.mine.zpool.ca (c=DOGE)

## Scan status
Full 84-repo GitHub audit performed pre-rebuild: no keyloggers, backdoors,
reverse shells, webhook exfiltration, or committed credentials found.
