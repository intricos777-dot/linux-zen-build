#!/usr/bin/env python3
"""Local stratum bridge: mine solo against your own daemon, no pool.

    miner  <--stratum+tcp-->  this  <--JSON-RPC-->  bitcoind/litecoind/...

A CPU or GPU miner speaks stratum; a daemon speaks getblocktemplate over
JSON-RPC. Something has to translate, and that is this. It is the same job
ckpool does, reduced to the single-wallet solo case and written in Python so it
can be read.

Each coin gets its own instance and its own daemon, each paying its own wallet.
There is no merged or dual mining anywhere here: Dogecoin dropped auxpow in
2014, so LTC and DOGE are two independent solo nodes and nothing more.

Only the standard library is used, so this runs anywhere python3 does.
"""

import argparse
import base64
import binascii
import http.client
import json
import logging
import os
import signal
import socket
import socketserver
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blockwork import (  # noqa: E402
    AddressError, address_to_script, block_hash, compact_to_target, dsha256,
    hash_below_target, make_coinbase, make_header, merkle_root, target_to_diff,
)

log = logging.getLogger("solo")


# ------------------------------------------------------------------ RPC


class RPCError(Exception):
    pass


class Daemon:
    """Minimal JSON-RPC client with cookie-file auth, like the bitcoind CLI."""

    def __init__(self, host="127.0.0.1", port=8332, user=None, password=None,
                 cookie=None, timeout=30.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.user = user
        self.password = password
        self.cookie = cookie
        self._id = 0
        self._lock = threading.Lock()

    def _auth_header(self):
        if self.cookie:
            try:
                with open(self.cookie, "r", encoding="utf-8") as fh:
                    creds = fh.read().strip()
            except OSError as e:
                # The cookie is written by the daemon on first start, so a
                # missing one almost always means "the node has never run",
                # which is worth saying plainly rather than as a traceback.
                raise RPCError(
                    "cannot read RPC cookie %s (%s). The node has not written "
                    "it yet, which means the daemon has not been started."
                    % (self.cookie, e.strerror))
            if not creds:
                raise RPCError("RPC cookie %s is empty; the daemon may still be "
                               "starting" % self.cookie)
        elif self.user is not None and self.password is not None:
            creds = "%s:%s" % (self.user, self.password)
        else:
            return {}
        token = base64.b64encode(creds.encode()).decode()
        return {"Authorization": "Basic " + token, "Content-Type": "application/json"}

    def call(self, method, *params):
        with self._lock:
            self._id += 1
            rid = self._id
        body = json.dumps({"jsonrpc": "1.0", "id": rid, "method": method,
                           "params": list(params)})
        headers = self._auth_header()
        headers["Content-Type"] = "application/json"
        conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            conn.request("POST", "/", body, headers)
            resp = conn.getresponse()
            raw = resp.read()
        except OSError as e:
            raise RPCError("cannot reach %s:%d (%s)" % (self.host, self.port, e))
        finally:
            conn.close()
        if resp.status == 401:
            raise RPCError("authentication rejected: check rpcuser/rpcpassword "
                           "or the cookie file for %s:%d" % (self.host, self.port))
        if resp.status != 200:
            raise RPCError("HTTP %d from %s:%d" % (resp.status, self.host, self.port))
        try:
            data = json.loads(raw)
        except ValueError:
            raise RPCError("non-JSON reply from daemon: %r" % raw[:200])
        if data.get("error"):
            err = data["error"]
            raise RPCError("%s: %s" % (err.get("code"), err.get("message")))
        return data.get("result")

    def getblocktemplate(self, capabilities=None, rules=None):
        params = {}
        if capabilities:
            params["capabilities"] = list(capabilities)
        if rules:
            params["rules"] = list(rules)
        return self.call("getblocktemplate", params)

    def submitblock(self, block_hex):
        """Returns None on acceptance, or a rejection reason string."""
        return self.call("submitblock", block_hex)

    def getblockchaininfo(self):
        return self.call("getblockchaininfo")


# ------------------------------------------------------------------ config


class ChainConfig:
    """Everything that differs between the four coins.

    `algo` is passed through to the miner, `p2p`/`rpc` are the daemon defaults,
    and `b58_versions` is what makes an address from one chain unacceptable on
    another.
    """

    def __init__(self, name, algo, p2p, rpc, b58_versions, segwit=False,
                 bip34=True, datadir="", cli="", service=""):
        self.name = name
        self.algo = algo
        self.p2p = p2p
        self.rpc = rpc
        self.b58_versions = set(b58_versions)
        self.segwit = segwit
        self.bip34 = bip34
        self.datadir = datadir
        # `cli` is the RPC client used to talk to the node; `service` is the
        # systemd unit that starts the node. They are different things and
        # conflating them produces "systemctl start bitcoin-cli".
        self.cli = cli
        self.service = service or (name + "d")


CHAINS = {
    # `service` is the actual systemd unit name on this system. Arch's bitcoin
    # package calls it bitcoind, not btcd, so the default would be wrong.
    "btc": ChainConfig("btc", "sha256d", 8333, 8332, {0x00, 0x05}, segwit=True,
                       datadir="~/.bitcoin", cli="bitcoin-cli", service="bitcoind"),
    "ltc": ChainConfig("ltc", "scrypt", 9333, 9332, {0x30, 0x32}, segwit=True,
                       datadir="~/.litecoin", cli="litecoin-cli", service="litecoind"),
    "doge": ChainConfig("doge", "scrypt", 22556, 22555, {0x1E, 0x16}, segwit=True,
                        datadir="~/.dogecoin", cli="dogecoin-cli", service="dogecoind"),
    "rvn": ChainConfig("rvn", "kawpow", 8767, 8766, {0x3E, 0x05}, segwit=False,
                       datadir="~/.ravencoin", cli="raven-cli", service="ravend"),
}


# ------------------------------------------------------------------ template


class Template:
    """A mined-on block template, turned into stratum job material."""

    def __init__(self, chain, address, gbt, extra_nonce=b"", share_diff=0.001):
        self.chain = chain
        self.address = address
        self.height = gbt["height"]
        self.previousblockhash = gbt["previousblockhash"]
        self.bits = int(gbt["bits"], 16)
        self.curtime = int(gbt["curtime"])
        self.version = int(gbt["version"])
        self.target = compact_to_target(self.bits)
        self.difficulty = target_to_diff(self.target)
        # The share target is deliberately far EASIER than the network target: a
        # share means "this miner is doing real work", not "this miner won".
        # A share difficulty of 0.001 means one share per thousand network
        # hashes, so the share target is the network target scaled UP by 1/diff.
        # Scaling it down instead would make every share harder than a block and
        # nothing would ever be accepted. Only the network target decides
        # whether a block is submitted.
        if share_diff and share_diff > 0:
            share_value = int(int.from_bytes(self.target, "big") / float(share_diff))
            self.share_target = share_value.to_bytes(32, "big")
        else:
            self.share_target = self.target
        self.script_pubkey = address_to_script(address, chain.b58_versions)

        # Coinbase commitment fields. getblocktemplate supplies these so the
        # coinbase we build is the one it will accept.
        self.coinbase_value = gbt["coinbasevalue"]
        self.coinbase_flags = gbt.get("default_witness_commitment") if chain.segwit else None

        self.txs = gbt.get("transactions") or []
        self.txids = gbt.get("transactionids") or []
        self.mutable = gbt.get("mutable", True)
        self.extra_nonce = extra_nonce

    def coinbase(self, extra_nonce=b""):
        return make_coinbase(
            height=self.height,
            script_pubkey=self.script_pubkey,
            value=self.coinbase_value,
            extra_script=extra_nonce,
            version=2 if self.chain.bip34 else 1,
        )

    def merkle_root_for(self, extra_nonce):
        cb = self.coinbase(extra_nonce)
        leaves = [dsha256(cb)] + [bytes.fromhex(t)[::-1] for t in self.txids]
        return merkle_root(leaves), cb

    def header_for(self, extra_nonce, nonce, ntime=None):
        root, _cb = self.merkle_root_for(extra_nonce)
        prev = bytes.fromhex(self.previousblockhash)[::-1]
        return make_header(
            version=self.version,
            prevhash_le=prev,
            merkleroot=root,
            ntime=self.curtime if ntime is None else ntime,
            nbits=self.bits,
            nonce=nonce,
        )

    def full_block_hex(self, extra_nonce, nonce, ntime=None):
        header = self.header_for(extra_nonce, nonce, ntime)
        cb = self.coinbase(extra_nonce)
        block = header + varint_(1 + len(self.txs)) + cb
        for tx in self.txs:
            block += bytes.fromhex(tx)
        return block.hex()


def varint_(n):
    if n < 0xFD:
        return struct.pack("<B", n)
    if n <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", n)
    if n <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", n)
    return b"\xff" + struct.pack("<Q", n)


# ------------------------------------------------------------------ stratum


class StratumClient(socketserver.BaseRequestHandler):
    """One connected miner."""

    def setup(self):
        self.server.clients.add(self)
        self.authorized = False
        self.extranonce2_size = 4
        self.pending = {}
        self.send_lock = threading.Lock()
        self.log_prefix = "?"

    def log_msg(self, fmt, *a):  # silence BaseRequestHandler logging
        pass

    def send(self, obj):
        line = json.dumps(obj) + "\n"
        with self.send_lock:
            try:
                self.request.sendall(line.encode())
            except OSError:
                pass

    def handle(self):
        peer = "%s:%d" % self.client_address[:2]
        self.log_prefix = peer
        log.info("miner connected from %s", peer)
        buf = b""
        self.request.settimeout(None)
        try:
            while True:
                data = self.request.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    self.dispatch(msg)
        except OSError:
            pass
        finally:
            self.server.clients.discard(self)
            log.info("miner %s disconnected", peer)

    def dispatch(self, msg):
        method = msg.get("method")
        params = msg.get("params") or []
        rid = msg.get("id")
        srv = self.server

        if method == "mining.subscribe":
            ex1 = os.urandom(4)
            self.extranonce2_size = srv.extranonce2_size
            if rid is not None:
                self.send({"id": rid, "result": [ex1.hex(), self.extranonce2_size],
                           "error": None})
            log.info("miner %s subscribed", self.log_prefix)
            return

        if method == "mining.authorize":
            user = params[0] if params else ""
            # In solo mode the username is ignored except to confirm the miner
            # is pointed here deliberately: the payout address comes from this
            # process's own config, never from the wire. That is what stops a
            # stray miner config from redirecting a found block.
            self.authorized = True
            if rid is not None:
                self.send({"id": rid, "result": True, "error": None})
            log.info("miner %s authorized as %r (paying %s)",
                     self.log_prefix, user, srv.address)
            srv.on_miner_online()
            self.send_current_job()
            return

        if method == "mining.extranonce.subscribe":
            self.extranonce2_size = int(params[0]) if params else 4
            if rid is not None:
                self.send({"id": rid, "result": True, "error": None})
            return

        if method == "mining.get_transactions":
            if rid is not None:
                self.send({"id": rid, "result": [], "error": None})
            return

        if method == "mining.submit":
            self.handle_submit(params, rid)
            return

        if rid is not None:
            self.send({"id": rid, "result": None,
                       "error": [20, "unknown method %s" % method, None]})

    def send_current_job(self):
        srv = self.server
        job = srv.current_job
        if not job:
            return
        self.send(srv.notify_for(job))
        self.send({"id": None, "method": "mining.set_difficulty",
                   "params": [srv.share_diff]})

    def handle_submit(self, params, rid):
        srv = self.server
        # params: [worker, job_id, extranonce2, ntime, nonce]
        if len(params) < 5:
            if rid is not None:
                self.send({"id": rid, "result": False,
                           "error": [20, "malformed submit", None]})
            return
        _worker, job_id, x2, ntime_hex, nonce_hex = params[:5]

        job = srv.jobs.get(job_id)
        if job is None:
            if rid is not None:
                self.send({"id": rid, "result": False,
                           "error": [21, "Job not found (stale)", None]})
            srv.stats["stale"] += 1
            return
        if job_id != srv.current_job_id:
            srv.stats["stale"] += 1

        try:
            miner_x2 = bytes.fromhex(x2)
            nonce = int(nonce_hex, 16)
            ntime = int(ntime_hex, 16)
        except (ValueError, TypeError):
            if rid is not None:
                self.send({"id": rid, "result": False,
                           "error": [20, "malformed submit", None]})
            return

        # The job's own extranonce2 is authoritative: it is what the merkle
        # root in mining.notify was computed over. A miner submitting something
        # else is still counted, but the block is rebuilt from the committed
        # value so that the header we verify is the header the miner proved.
        extra = job["extranonce2_bytes"]
        if miner_x2 and miner_x2 != extra:
            srv.stats["x2_mismatch"] += 1

        header = job["template"].header_for(extra, nonce, ntime)
        # Display order, because both targets are display order. Comparing the
        # raw dsha256() against them inverts the test and the rig accepts
        # nothing at all while reporting shares as fine.
        digest = block_hash(header)
        tpl = job["template"]

        # Gate one: is this a share at all? Under the share difficulty, not the
        # network difficulty. Without this the bridge would discard the easy
        # early shares a miner sends while ramping up.
        if not hash_below_target(digest, tpl.share_target):
            srv.stats["weak"] += 1
            if rid is not None:
                self.send({"id": rid, "result": False,
                           "error": [23, "Low difficulty share", None]})
            return
        srv.stats["accepted"] += 1

        # Gate two: is it a block? Only the real network target can say so.
        if not hash_below_target(digest, tpl.target):
            if rid is not None:
                self.send({"id": rid, "result": True, "error": None})
            return

        # Below the real target: this is a solved block.
        block_hex = tpl.full_block_hex(extra, nonce, ntime)
        log.warning("BLOCK FOUND %s at height %d, submitting",
                    job["template"].height, job["template"].height)
        try:
            result = srv.daemon.submitblock(block_hex)
        except RPCError as e:
            log.error("submitblock failed: %s", e)
            if rid is not None:
                self.send({"id": rid, "result": True, "error": None})
            return
        if result:
            log.error("BLOCK REJECTED by network: %s", result)
        else:
            log.warning("BLOCK ACCEPTED: %s height %d pays %s",
                        job["template"].previousblockhash, job["template"].height,
                        job["template"].address)
        srv.stats["blocks"] += 1
        if rid is not None:
            self.send({"id": rid, "result": True, "error": None})


class StratumServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr, chain, daemon, address, share_diff=0.001,
                 extranonce2_size=4):
        self.chain = chain
        self.daemon = daemon
        self.address = address
        self.share_diff = share_diff
        self.extranonce2_size = extranonce2_size
        self.clients = set()
        self.jobs = {}
        self.current_job = None
        self.current_job_id = None
        self.job_counter = 0
        self.stats = {"accepted": 0, "weak": 0, "stale": 0, "blocks": 0,
                      "x2_mismatch": 0}
        self.stopping = threading.Event()
        super().__init__(addr, StratumClient)

    def on_miner_online(self):
        pass

    def notify_for(self, job):
        t = job["template"]
        return {
            "id": None,
            "method": "mining.notify",
            "params": [
                job["id"],
                t.previousblockhash,
                job["merkle_root"][::-1].hex(),
                "%08x" % t.version,
                "%08x" % t.curtime,
                "%08x" % t.bits,
            ],
        }

    def broadcast(self, obj):
        for c in list(self.clients):
            c.send(obj)

    def new_job(self, tpl):
        self.job_counter += 1
        job_id = "%d" % self.job_counter
        # Each job commits a fresh random value into its coinbase, so two
        # jobs on the same template produce different blocks and a miner that
        # only ever sweeps one nonce still does new work each time.
        #
        # This value, not the miner's submitted extranonce2, is what the merkle
        # root was built over, so it is what must be used to rebuild the block.
        # The miner varied the 32 bit header nonce, which is the field a CPU or
        # GPU miner actually sweeps; rebuilding from a different extranonce2
        # would produce a block that does not correspond to the header the
        # miner proved, and the network would reject it.
        x2 = os.urandom(self.extranonce2_size)
        merkle, _cb = tpl.merkle_root_for(x2)
        job = {"id": job_id, "template": tpl, "merkle_root": merkle,
               "extranonce2_bytes": x2}
        self.jobs = {job_id: job}
        self.current_job = job
        self.current_job_id = job_id
        self.broadcast({"id": None, "method": "mining.set_difficulty",
                        "params": [self.share_diff]})
        self.broadcast(self.notify_for(job))
        log.info("new %s job %s: height %d difficulty %.4g bits %08x",
                 tpl.chain.name, job_id, tpl.height, tpl.difficulty, tpl.bits)
        return job

    def poll_loop(self, interval, stop):
        rules = ["segwit"] if self.chain.segwit else None
        caps = ["coinbase/append", "coinbasetxn", "workid", "coinvalue"]
        while not stop.is_set():
            try:
                gbt = self.daemon.getblocktemplate(capabilities=caps, rules=rules)
            except RPCError as e:
                log.warning("getblocktemplate failed: %s", e)
                if stop.wait(interval * 3):
                    return
                continue
            if not gbt:
                if stop.wait(interval * 3):
                    return
                continue
            try:
                tpl = Template(self.chain, self.address, gbt,
                               share_diff=self.share_diff)
            except (KeyError, ValueError, AddressError) as e:
                log.error("cannot use template: %s", e)
                if stop.wait(interval * 3):
                    return
                continue
            prev = self.current_job["template"].previousblockhash \
                if self.current_job else None
            if prev != tpl.previousblockhash or not self.current_job:
                self.new_job(tpl)
            stop.wait(interval)

    def status_line(self):
        j = self.current_job
        if not j:
            return "no job yet"
        t = j["template"]
        return ("height %d, difficulty %.6g, bits %08x, miners %d, "
                "shares %d (weak %d), stale %d, blocks %d"
                % (t.height, t.difficulty, t.bits, len(self.clients),
                   self.stats["accepted"], self.stats["weak"],
                   self.stats["stale"], self.stats["blocks"]))


# ------------------------------------------------------------------ main


def load_config(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--config", required=True,
                    help="JSON config file for this coin")
    ap.add_argument("-l", "--listen", default="127.0.0.1",
                    help="address to bind stratum to (default 127.0.0.1, local only)")
    ap.add_argument("-p", "--port", type=int, help="stratum port (default from config)")
    ap.add_argument("--check", action="store_true",
                    help="verify config and daemon, then exit without mining")
    ap.add_argument("--share-diff", type=float, help="override share difficulty")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S")

    cfg = load_config(args.config)
    chain_name = cfg.get("chain", "").lower()
    if chain_name not in CHAINS:
        ap.error("unknown chain %r; expected one of %s"
                 % (chain_name, ", ".join(sorted(CHAINS))))
    chain = CHAINS[chain_name]

    address = cfg.get("address", "")
    try:
        address_to_script(address, chain.b58_versions)
    except AddressError as e:
        ap.error("payout address rejected: %s\n"
                 "Fix \"address\" in %s. Nothing is mined until this is a valid "
                 "%s address." % (e, args.config, chain_name.upper()))

    cookie = cfg.get("cookie")
    if cookie:
        cookie = os.path.expanduser(cookie)
    user = cfg.get("rpcuser")
    password = cfg.get("rpcpassword")
    if not cookie and (not user or password is None):
        ap.error("need either \"cookie\" (preferred) or \"rpcuser\"+\"rpcpassword\"")

    daemon = Daemon(host=cfg.get("rpchost", "127.0.0.1"),
                    port=int(cfg.get("rpcport", chain.rpc)),
                    user=user, password=password, cookie=cookie)

    port = args.port or int(cfg.get("stratum_port", 3333))
    share_diff = args.share_diff or float(cfg.get("share_diff", 0.001))
    poll = float(cfg.get("poll_seconds", 1.0))
    extranonce2_size = int(cfg.get("extranonce2_size", 4))

    log.info("%s solo bridge: stratum %s:%d -> %s:%d, paying %s",
             chain.name.upper(), args.listen, port,
             cfg.get("rpchost", "127.0.0.1"), daemon.port, address)

    try:
        info = daemon.getblockchaininfo()
    except RPCError as e:
        daemon_cmd = chain.service
        ap.error("daemon not ready: %s\n"
                 "Start it and let it finish the initial block download:\n"
                 "    sudo systemctl start %s.service\n"
                 "There is nothing to mine against until the node has the full "
                 "chain, and a pool is not the answer if you want solo."
                 % (e, daemon_cmd))
    log.info("daemon chain=%s blocks=%d headers=%d",
             info.get("chain"), info.get("blocks"), info.get("headers"))
    if info.get("chain") != chain.name and info.get("chain") != "main":
        ap.error("daemon is on chain %r but config says %r"
                 % (info.get("chain"), chain.name))
    if info.get("initialblockdownload"):
        log.warning("daemon reports initial block download in progress; "
                    "mining will not find anything until it finishes")
    if info.get("pruned"):
        log.warning("daemon is pruned; fine for mining, it keeps the UTXO set")

    if args.check:
        print("config OK: %s, address %s valid for %s, daemon reachable at %s:%d"
              % (cfg.get("chain"), address, chain_name.upper(),
                 cfg.get("rpchost", "127.0.0.1"), daemon.port))
        return 0

    server = StratumServer((args.listen, port), chain, daemon, address,
                           share_diff=share_diff,
                           extranonce2_size=extranonce2_size)
    stop = threading.Event()

    def shutdown(_signum, _frame):
        log.info("shutting down")
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    poller = threading.Thread(target=server.poll_loop, args=(poll, stop), daemon=True)
    poller.start()

    def heartbeat():
        while not stop.wait(900):
            log.info("status: %s", server.status_line())

    threading.Thread(target=heartbeat, daemon=True).start()

    log.info("listening. Point the miner at stratum+tcp://%s:%d", args.listen, port)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop.set()
        server.server_close()
    log.info("final: %s", server.status_line())
    return 0


if __name__ == "__main__":
    sys.exit(main())
