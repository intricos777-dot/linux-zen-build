# True solo mining: BTC, LTC, DOGE, RVN

Four independent solo miners, each mining against its own local full node. No
pool, no dev fee, no shared ledger, 100% of any block reward.

This replaces the earlier scripts in this directory, which were named `solo`
but pointed at `ltc.viabtc.io`, `scrypt.mine.zpool.ca` and `solo.ckpool.org`.
Those were pool mining with the word solo in the filename. They are gone.

## What "solo" means here, concretely

```
CPU/GPU miner ──stratum+tcp://127.0.0.1──> solo_bridge.py ──JSON-RPC──> bitcoind
                                                                    litecoind
                                                                    dogecoind
                                                                    ravend
```

The bridge is what makes it real. A miner speaks stratum; a daemon speaks
`getblocktemplate` over JSON-RPC. Something has to translate, and if that
something is a public pool then you are not solo. `solo_bridge.py` is that
something, in about 500 lines of readable Python using only the standard
library. It is the same job `ckpool` does, reduced to the single-wallet solo
case.

## Three things this deliberately does not do

**No GPU Bitcoin miner.** SHA-256 has been ASIC-only since roughly 2013. The
RTX 3050 in this machine cannot compete with an ASIC, and no flag, driver or
config file changes that. There is no useful GPU BTC miner to add, so none is
here. BTC is CPU-only, and it is a lottery ticket either way.

**No merged LTC+DOGE mining.** Dogecoin removed auxpow (merged mining) in
2014. There has been no LTC+DOGE "dual mining" since. LTC and DOGE are two
separate chains with two separate daemons and two separate rewards; a shared
stratum endpoint would mine one chain and pay the other chain's address, which
is unspendable. They run as two independent solo nodes that happen to share a
machine.

**No invented wallet addresses.** Two of the four are unusable as recorded, and
the tooling refuses to start rather than hash toward a payout that can never be
spent. See the table below.

## Wallets

| Coin | Address | State |
| --- | --- | --- |
| BTC | `33oBrFCtn7SvqULsERymwtwmM8mXSrgcd9` | valid. base58check OK, version `0x05` (P2SH) |
| LTC | `MQ3qudKtDzSmwg7tHUV7JZTXizLYBtzffj` | valid. base58check OK, version `0x32` = Litecoin P2SH |
| DOGE | `Dai6AHB6D4M152PWjnHNFF8v` | **INVALID** |
| RVN | — | **none on record** |

Both were carried over verbatim from this repo's README. The BTC and LTC ones
verify. The other two do not, and the specifics matter:

**DOGE `Dai6AHB6D4M152PWjnHNFF8v` is not a Dogecoin address.** Three
independent problems: it is 24 characters, too short for a base58check
Dogecoin address; its checksum is `4701e383` where the payload hashes to
`c143cf13`; and its version byte is `0x05`, which is a *Bitcoin* P2SH version.
Dogecoin uses `0x1e` (P2PKH) and `0x16` (P2SH). It is preserved in
`configs/doge.json` exactly as recorded, because deleting the owner's recorded
value would hide the fact that it is wrong, and the DOGE service refuses to
start while it is in place.

```bash
dogecoin-cli -datadir=~/.dogecoin getnewaddress
```

**RVN has no address at all.** None is recorded anywhere in this repository
and none was invented. `configs/rvn.json` carries a marked placeholder:

```bash
raven-cli -datadir=~/.ravencoin getnewaddress
```

Solo mining pays the entire block reward to the configured address, so a wrong
address is a total loss rather than a small fee. That asymmetry is why the code
validates addresses per chain and refuses to start on anything suspect, instead
of passing a string through and hoping.

## Install

Nothing in this repo runs a root command for you. Read the installer, then run
it yourself:

```bash
less install-solo-miners.sh
sudo ./install-solo-miners.sh --plan     # prints the plan, changes nothing
sudo ./install-solo-miners.sh --check    # reports what is present, changes nothing
sudo ./install-solo-miners.sh            # installs, after a y/N prompt
```

Staged, and safe to re-run — each stage checks what is already there first:

```bash
sudo ./install-solo-miners.sh --daemons   # nodes only
sudo ./install-solo-miners.sh --miners    # miner binaries only
sudo ./install-solo-miners.sh --services  # bridge + systemd units only
```

Idempotency: packages already installed are skipped, existing configs are
overwritten only with identical content, and units are rewritten from the same
template each time. Nothing stops or restarts a running service unless that
service's own unit file changed.

It installs:

| Stage | What | Where from |
| --- | --- | --- |
| daemons | `bitcoind`, `bitcoin-cli` | Arch official repos |
| daemons | `litecoind` 0.21.5.8 | AUR |
| daemons | `dogecoind` 1.14.9 | AUR |
| daemons | `ravend` | **UNAVAILABLE — see below** |
| miners | `cpuminer-opt` | AUR (CPU: sha256d, scrypt) |
| miners | `gminer-bin` | AUR (GPU: kawpow only) |
| services | bridge, configs, 3 user units | `/var/lib/solo-miners`, `/etc/systemd/system` |

Services run as your user, never root. A miner is a network-facing program fed
remote data by design; running one as root is indefensible. Units are hardened
(`NoNewPrivileges`, `ProtectSystem=strict`, `RestrictSUIDSGID`) and bind
stratum to loopback only, because a solo rig pays full block rewards to
whoever can reach it.

For the services to survive logout:

```bash
sudo loginctl enable-linger "$USER"
```

## Ravencoin is not installable yet

Ravencoin Core is in neither the Arch binary repos nor the AUR under a usable
name — the AUR carries `raven-qt` and `electrum-ravencoin`, which are wallets,
not full nodes, and neither provides a `getblocktemplate` to mine against. The
installer marks the stage `UNAVAILABLE`, creates no `solo-rvn` unit, and
downloads nothing.

The GPU miner script is written and correct; it will run as soon as a `ravend`
exists. Two supported routes — building from `RavenProject/Ravencoin` source,
or tunnelling a `ravend` you already run — are in
[docs/RVN-NODE-GAP.md](docs/RVN-NODE-GAP.md).

## Running it

Sync first. Mining against a node that is still in its initial block download
finds nothing, and looks like working hardware doing nothing.

```bash
bitcoind -datadir=~/.bitcoin getblockchaininfo | grep -E 'blocks|initialblock'
```

Start the bridge, then the miner, per coin:

```bash
# terminal 1
python3 solo/solo_bridge.py -c solo/configs/btc.json
# terminal 2
./mine-btc-cpu-solo.sh
```

Or as services:

```bash
systemctl --user start solo-btc
./mine-btc-cpu-solo.sh
```

| Coin | Bridge | Miner | Algorithm | Device |
| --- | --- | --- | --- | --- |
| BTC | `solo/configs/btc.json` (3333) | `mine-btc-cpu-solo.sh` | sha256d | CPU |
| LTC | `solo/configs/ltc.json` (3334) | `mine-ltc-solo.sh` | scrypt | CPU |
| DOGE | `solo/configs/doge.json` (3335) | `mine-doge-solo.sh` | scrypt | CPU |
| RVN | `solo/configs/rvn.json` (3336) | `mine-rvn-gpu.sh` | kawpow | GPU |

Every miner script refuses to start if nothing is listening on its stratum
port, and tells you to start the bridge. Pointing a miner at a pool is the one
thing that would quietly make this not-solo, so there is no fallback path
anywhere in these scripts.

Validate a config without mining:

```bash
python3 solo/solo_bridge.py -c solo/configs/btc.json --check
```

## Tests

The block construction is checked against published vectors rather than against
a running daemon, because a wrong merkle root or a wrong BIP34 push produces a
rig that runs happily for months and never finds anything.

```bash
python3 solo/test_blockwork.py       # 26 tests
python3 solo/test_solo_bridge.py     # 20 tests
```

`test_blockwork.py` reconstructs the Bitcoin genesis block and asserts it
hashes to
`000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f`, folds
merkle trees with the odd-leaf duplication rule, checks BIP34 CScriptNum
encoding including the sign pad, and round-trips `nBits` across 50,000 random
mainnet-shaped values against a transcription of Core's `GetCompact`.

`test_solo_bridge.py` stands up a fake daemon and a real bridge, connects a
real stratum client, and drives a share all the way through — including finding
an actual block and checking the submitted bytes are a well-formed block whose
header hashes to what the share claimed.

Three real bugs were caught by these tests and fixed:

1. The share check compared a raw `dsha256()` (internal byte order) against a
   big-endian target, inverting the difficulty test. Nothing could ever be
   accepted while the log looked healthy. `block_hash()` now exists so the
   conversion has one name and one direction.
2. The share target was scaled *down* by the share difficulty, making every
   share harder than a block. It is scaled up.
3. The bridge committed one extranonce2 into the merkle root and then
   concatenated the miner's on top when rebuilding, so the reconstructed block
   did not match the header the miner had proved.

## Honest expectations

Solo mining on this hardware finds a block roughly never, and it is worth
being blunt about the arithmetic rather than implying otherwise.

Bitcoin solo needs on the order of 10^21 hashes per block at current
difficulty. This CPU does roughly 10^6 hashes per second — call it 10^5 to 10^6
useful hashes per second given that a solo miner is also feeding a stratum
bridge. That is a gap of fifteen orders of magnitude. Running this does not
lose money, but it does not make any either.

Ravencoin is the only one of the four where a GPU is the right tool, because
KAWPOW was designed for GPUs. Even there, a single RTX 3050 Mobile is a
fraction of a percent of network hashrate, so the expected wait is long.

What this setup actually buys: the work is genuine solo work, the payout path
is verified end to end, no pool takes a cut, and nothing is silently pointed
somewhere you did not intend. The block-finding is not going to happen.

## Layout

```
miners/
  install-solo-miners.sh     staged, idempotent, root, you run it
  mine-btc-cpu-solo.sh       sha256d on CPU against local bitcoind
  mine-ltc-solo.sh           scrypt on CPU against local litecoind
  mine-doge-solo.sh          scrypt on CPU against local dogecoind
  mine-rvn-gpu.sh            kawpow on GPU against local ravend
  docs/RVN-NODE-GAP.md       why there is no ravencoin package, and what to do
  solo/
    solo_bridge.py           stratum <-> getblocktemplate, stdlib only
    blockwork.py             block construction primitives, pure functions
    test_blockwork.py        26 tests, published vectors
    test_solo_bridge.py      20 tests, live bridge against a fake daemon
    configs/{btc,ltc,doge,rvn}.json
  retain_blocks.py           pre-existing; confirmed-block log retention
  retain-cache.sh
```

`retain_blocks.py` and `retain-cache.sh` are unrelated to the pool problem and
are unchanged.
