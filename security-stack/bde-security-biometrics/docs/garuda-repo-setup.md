<!-- Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work -->
# Garuda Linux / BlackArch pacman repo setup

BDE packages are GPG-signed. **An unsigned or mis-signed package is rejected.**
Do not weaken `SigLevel` on this repo — see "Why not TrustAll" below.

## 1. Trust the signing key

Do this **before** enabling the repo, or every install will fail verification.

```bash
# Fetch the key and read its fingerprint
curl -fsSL https://repo.intricos777-dot.com/bde-security-biometrics/arch/bde-key.asc -o /tmp/bde-key.asc
gpg --show-keys --with-fingerprint /tmp/bde-key.asc
```

Check the fingerprint against the one published in the project README. It must
match exactly. If it does not, **stop** — you may have been given a forged key.

```bash
# Import, then locally sign it. --lsign-key sets ownertrust to ultimate, which
# is what pacman requires; --add alone leaves the key only marginally trusted.
sudo pacman-key --add /tmp/bde-key.asc
sudo pacman-key --lsign-key <FINGERPRINT>
rm -f /tmp/bde-key.asc
```

## 2. Add the repo

Place it **above `[extra]`** in `/etc/pacman.conf`:

```ini
[bde-security-biometrics]
Server = https://repo.intricos777-dot.com/bde-security-biometrics/arch/
SigLevel = Required DatabaseOptional
```

What that means:

| Setting | Effect |
|---|---|
| `Required` | Every package **must** carry a valid signature. Unsigned packages are refused. |
| `DatabaseOptional` | The repo index may be unsigned. Package signatures are still mandatory. |

`DatabaseOptional` is the Arch default because the index is a signed-by-hash
manifest; the packages themselves carry the real signature. If you want the
index signed too, use `Required DatabaseRequired`.

Install:

```bash
sudo pacman -Syy
sudo pacman -S bde-security-biometrics
```

## Why not TrustAll

`SigLevel = Optional TrustAll` accepts **any** signature, including one from a
key you have never seen. It also accepts **no** signature at all. On a
biometric authenticator that gates your login, that means anyone who can serve
you a package — a compromised mirror, a hijacked DNS record, a typo'd hostname —
can run code as root with no warning.

`Required DatabaseOptional` fails closed. An attacker without your signing key
gets a refusal, not a silent install.

## BlackArch

Compatible. This repo layers BDE biometrics on top of BlackArch tooling and
inherits BlackArch's own signing policy for its own packages.
