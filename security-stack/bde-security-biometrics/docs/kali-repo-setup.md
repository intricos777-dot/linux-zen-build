<!-- Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work -->
# Kali Linux apt repo setup

BDE packages are GPG-signed and the repo is pinned to a dedicated keyring.
**Unsigned packages are refused.**

## 1. Add the keyring

```bash
sudo apt-get install -y gnupg
curl -fsSL https://repo.intricos777-dot.com/bde-security-biometrics/debian/gpg.key \
  | sudo gpg --dearmor -o /usr/share/keyrings/bde-security-biometrics-archive-keyring.gpg
```

Verify the key fingerprint against the project README before trusting it:

```bash
gpg --show-keys --with-fingerprint \
  /usr/share/keyrings/bde-security-biometrics-archive-keyring.gpg
```

If it does not match, **stop**.

## 2. Add the repo, pinned to that keyring

```bash
echo "deb [signed-by=/usr/share/keyrings/bde-security-biometrics-archive-keyring.gpg] https://repo.intricos777-dot.com/bde-security-biometrics/debian kali-rolling main" | \
  sudo tee /etc/apt/sources.list.d/bde-security-biometrics.list
sudo apt-get update
sudo apt-get install bde-security-biometrics
```

`signed-by=` is the important part. It scopes this one repo to this one key, so
the package cannot be satisfied by any other key in the system keyring — and a
package signed by an unrelated key is rejected rather than silently trusted.

## Why the keyring is scoped

Without `signed-by=`, apt will accept the package if *any* trusted key in
`/etc/apt/trusted.gpg.d` signed it, and will offer it for install even when
unauthenticated. Scoping the trust to one file means an unrelated key — or no
key at all — produces a hard failure.
