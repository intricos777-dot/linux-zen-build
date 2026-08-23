# Kali Linux apt repo setup

## Add BDE repo

```bash
echo "deb https://repo.intricos777-dot.com/bde-security-biometrics/debian kali-rolling main" | \
  sudo tee /etc/apt/sources.list.d/bde-security-biometrics.list
sudo -S -p '' apt update && sudo -S -p '' apt install bde-security-biometrics
```

Keys:
```bash
sudo -S -p '' apt install -y gnupg
curl -fsSL https://repo.intricos777-dot.com/bde-security-biometrics/debian/gpg.key | \
  sudo gpg --dearmor -o /usr/share/keyrings/bde-security-biometrics-archive-keyring.gpg
```
