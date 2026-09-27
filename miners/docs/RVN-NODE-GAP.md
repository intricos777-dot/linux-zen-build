# Ravencoin node: the packaging gap, and the two real ways through it

## The gap

There is no Ravencoin Core package to install on this machine, and the
installer says so rather than working around it.

Checked against the live repositories:

| Source | Result |
| --- | --- |
| Arch binary repos (`extra`, `core`, `multilib`) | no Ravencoin Core |
| AUR, searched for `ravencoin` | `electrum-ravencoin-appimage` only |
| AUR, searched for `raven` | `raven` 0.21.1 (a Java rules engine, unrelated), `raven-qt` 4.6.1, `raven-bin` — wallets, **not** full nodes |

`raven-qt` is the Ravencoin Core Qt wallet. It ships `raven-qt` and
`raven-cli`, and the wallet is not a full node: without `ravend` there is no
chain database, no `getblocktemplate`, and therefore nothing to mine against.
An `electrum-*` package talks to somebody else's server, which is the opposite
of solo.

So the honest position: the RVN GPU miner is written and correct, but it cannot
run until a `ravend` exists. The installer therefore marks the ravencoin stage
`UNAVAILABLE`, does not create `solo-rvn.service`, and does not fetch an
unverified binary from somewhere convenient and call it a node.

## Two ways forward

### Option A — build Ravencoin Core from source

The upstream repository is `RavenProject/Ravencoin` (the
`ravencoin-community/ravencoin-core` name no longer resolves; 404 as of
2026-09). It is a Bitcoin Core fork and builds the usual way.

Verified from that tree, master branch:

- `src/chainparamsbase.cpp` → `RPCPort = 8766` (mainnet)
- `src/chainparams.cpp` → `nDefaultPort = 8767` (mainnet P2P)
- `src/rpc/mining.cpp` → `getblocktemplate` present, `getworktemplate` absent

The absence of `getworktemplate` is the important one, and it applies to all
four coins in this repo. Bitcoin Core removed it in v30, and the forks
inherited that. So the bridge in `solo/` is built on `getblocktemplate`, which
is the only interface any of these daemons offer for building work.

Roughly:

```bash
sudo pacman -S --needed base-devel git openssl libevent cmake \
     python m4 autoconf automake libtool boost qt5-base
git clone https://github.com/RavenProject/Ravencoin
cd Ravencoin
./autogen.sh
./configure --prefix=/usr/local --with-gui=qt5
make -j"$(nproc)"
sudo make install
```

This is a real build of a real project, but it is also a substantial
dependency chain and it is **not** something this repo should do behind your
back. If you take this route, the AUR will shortly have a maintained
`ravencoin-core` PKGBUILD; check before building by hand:

```bash
paru -Ss ravencoin
```

If one has appeared, install that instead and delete the manual build.

### Option B — run ravend elsewhere, tunnel the RPC

If you have another machine (a NAS, a VPS, a spare desktop) that can hold the
Ravencoin chain, run the full node there and forward its RPC port to this one
over an SSH tunnel. Only the RPC port needs to cross; the stratum port stays on
loopback here.

On the node host:

```
# ravend.conf
server=1
listen=0
rpcallowip=10.0.0.0/24
```

On this machine:

```bash
ssh -N -L 8766:127.0.0.1:8766 user@node-host
```

Then point `configs/rvn.json` at it:

```json
{
  "chain": "rvn",
  "address": "YOUR_REAL_ADDRESS",
  "rpcuser": "solo",
  "rpcpassword": "REAL_PASSWORD",
  "rpchost": "127.0.0.1",
  "rpcport": 8766
}
```

`rpchost` stays `127.0.0.1` because the tunnel terminates locally, and the
bridge still never binds its stratum port off loopback. Nothing about the
mining changes: it is still a real solo rig against a real full node you
control.

Caveat worth stating: with cookie auth the cookie lives on the node host, so
use explicit `rpcuser`/`rpcpassword` over the tunnel and keep
`rpcallowip` narrow. An SSH tunnel is encrypted; a bare `rpcallowip=0.0.0.0/0`
on a port-forwarded RPC is not.

## What still has to be supplied either way

**A Ravencoin address.** None exists anywhere in this repository, and none has
been invented. `configs/rvn.json` holds a marked placeholder and both the
bridge and `mine-rvn-gpu.sh` refuse to start while it is in place, because a
solo rig pays the whole block reward to whatever address is configured, and a
typo there loses all of it.

```bash
raven-cli -datadir=/var/lib/raven getnewaddress
```

## Why the GPU, and only here

Ravencoin's KAWPOW is ProgPoW-derived and was designed to be GPU-minable.
That is the entire reason it exists as a separate choice from Bitcoin's
SHA-256, which was left to ASICs from around 2013. An RTX 3050 Mobile is a
realistic (if small) KawPoW miner. It is not a realistic SHA-256 miner, and no
configuration change makes it one.

## Honest expectations

Solo RVN on one mobile GPU is a fraction of a percent of network hashrate, so
the expected time to a block is long — months to years. The value here is that
the work is real solo work, the payout path is verified, and no pool takes a
cut. It is not income.
