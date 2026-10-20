#!/usr/bin/env python3
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
"""End-to-end tests for the solo bridge, against a fake daemon.

A real end-to-end run: start a fake coin daemon that speaks getblocktemplate
over HTTP, start the bridge in front of it, connect a stratum client, mine a
share, and check the bridge did the right thing with it. That is the only way
to know the wiring is right, because the failure mode of a solo rig is that it
runs happily for months and never submits anything.
"""

import hashlib
import json
import os
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import solo_bridge  # noqa: E402
from blockwork import (  # noqa: E402
    AddressError, address_to_script, block_hash, compact_to_target, dsha256,
    hash_below_target,
)


def find_valid_nonce(tpl, x2, target=None, limit=200000):
    """Search for a nonce that satisfies `target`, defaulting to the network one."""
    target = target if target is not None else tpl.target
    for i in range(limit):
        if hash_below_target(block_hash(tpl.header_for(x2, i)), target):
            return i
    return None

# The Bitcoin genesis coinbase, reused as a stand-in "mempool transaction" so
# the merkle path has more than one leaf to fold.
FAKE_TX = ("0100000001" + "aa" * 32 + "00000000" + "00" + "ffffffff"
           "01" + "e803000000000000" + "19" + "76a914" + "bb" * 20 + "88ac"
           "ffffffff" + "01" + "2c8b070000000000" + "19" + "76a914" + "cc" * 20 +
           "88ac" + "00000000")

# The real difficulty-1 target. Note this is genuinely 1-in-4-billion, not 50%
# per hash, so a test cannot rely on finding a block at this difficulty.
DIFF1_BITS = 0x1D00FFFF

# A deliberately absurd target for the fake daemon: exponent 0x1f with a tiny
# mantissa puts the target near the top of the 256-bit range, so roughly one
# nonce in a few thousand solves. This is what lets the tests actually reach
# the block-submission path instead of only the share path.
EASY_BITS = 0x1F0FFFF0

# An address the test rig controls, so a solved block is observable.
TEST_ADDRESS = "33oBrFCtn7SvqULsERymwtwmM8mXSrgcd9"


class FakeDaemonHandler(BaseHTTPRequestHandler):
    """Serves getblocktemplate / submitblock / getblockchaininfo."""

    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        method = body.get("method")
        self.server.auth_seen = self.headers.get("Authorization")

        if method == "getblockchaininfo":
            result = {"chain": "main", "blocks": 800000, "headers": 800000,
                      "initialblockdownload": False, "pruned": False}
        elif method == "getblocktemplate":
            result = {
                "version": 0x20000000,
                "previousblockhash": "00" * 32,
                "transactions": [FAKE_TX],
                "transactionids": [dsha256(bytes.fromhex(FAKE_TX))[::-1].hex()],
                "coinbasevalue": 625000000,
                "coinbasetxn": "",
                "coinbaseaux": {},
                "mintime": 1231006505,
                "curtime": 1231006505,
                "bits": "%08x" % EASY_BITS,
                "height": 800000,
                "default_witness_commitment":
                    "6a24aa21a9ed" + "bb" * 32,
                "mutable": True,
            }
        elif method == "submitblock":
            self.server.submitted.append(body["params"][0])
            result = None
        else:
            result = None

        out = json.dumps({"result": result, "error": None, "id": body.get("id")})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out.encode())


class TestBridgeEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", 0), FakeDaemonHandler)
        cls.httpd.submitted = []
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.rpc_port = cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.bridge = None
        self.sock = None

    def tearDown(self):
        if self.sock:
            self.sock.close()
        if self.bridge:
            self.bridge.stopping.set()
            self.bridge.shutdown()
            self.bridge.server_close()

    def start_bridge(self, share_diff=0.001):
        chain = solo_bridge.CHAINS["btc"]
        daemon = solo_bridge.Daemon(host="127.0.0.1", port=self.rpc_port,
                                    user="u", password="p")
        # Port 0 lets the OS pick, so tests never collide.
        bridge = solo_bridge.StratumServer(("127.0.0.1", 0), chain, daemon,
                                           TEST_ADDRESS, share_diff=share_diff)
        threading.Thread(target=bridge.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True).start()
        threading.Thread(target=bridge.poll_loop, args=(0.05, bridge.stopping),
                         daemon=True).start()
        self.bridge = bridge
        return bridge

    def connect(self, bridge):
        self.sock = socket.create_connection(bridge.server_address, timeout=5)
        f = self.sock.makefile("rwb")

        def rpc(method, params=None, rid=1):
            f.write((json.dumps({"id": rid, "method": method,
                                 "params": params or []}) + "\n").encode())
            f.flush()
            while True:
                line = f.readline()
                if not line:
                    raise AssertionError("bridge closed the connection")
                msg = json.loads(line)
                if msg.get("id") == rid:
                    return msg

        rpc("mining.subscribe", [], 1)
        rpc("mining.authorize", [TEST_ADDRESS, "x"], 2)
        return f, rpc

    def wait_for(self, predicate, timeout=5.0):
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.02)
        return False

    # ---------------------------------------------------------------- tests

    def test_template_produces_a_valid_merkle_root_and_header(self):
        bridge = self.start_bridge()
        self.assertTrue(self.wait_for(lambda: bridge.current_job),
                        "bridge never produced a job")
        job = bridge.current_job
        tpl = job["template"]
        self.assertEqual(tpl.height, 800000)
        # The fake target is easier than difficulty 1, so the reported
        # difficulty must be correspondingly below 1.
        self.assertLess(tpl.difficulty, 1.0)
        # The share target is scaled UP, i.e. easier than the network target,
        # which is the whole point: shares are cheap, blocks are not.
        self.assertGreater(int.from_bytes(tpl.share_target, "big"),
                           int.from_bytes(tpl.target, "big"))
        self.assertEqual(int.from_bytes(tpl.share_target, "big"),
                         int(int.from_bytes(tpl.target, "big") / 0.001))
        # The coinbase must actually be in the merkle leaves, folded with the
        # mempool transaction. A wrong order here silently invalidates every
        # block the rig could ever find.
        from blockwork import merkle_root
        # getblocktemplate hands txids over in display order; the merkle tree
        # is built from internal order, so they must be reversed on the way in.
        leaves = [dsha256(tpl.coinbase(job["extranonce2_bytes"])),
                  bytes.fromhex(tpl.txids[0])[::-1]]
        self.assertEqual(job["merkle_root"], merkle_root(leaves))
        # And it must not equal the unreversed form, which would be the bug.
        self.assertNotEqual(
            job["merkle_root"],
            merkle_root([dsha256(tpl.coinbase(job["extranonce2_bytes"])),
                         bytes.fromhex(tpl.txids[0])]))

    def test_header_is_eighty_bytes_and_uses_the_template_fields(self):
        bridge = self.start_bridge()
        self.assertTrue(self.wait_for(lambda: bridge.current_job))
        tpl = bridge.current_job["template"]
        header = tpl.header_for(b"\x01\x02\x03\x04", 0xDEADBEEF)
        self.assertEqual(len(header), 80)
        # Field layout: version | prevhash | merkle root | time | bits | nonce
        self.assertEqual(int.from_bytes(header[0:4], "little"), 0x20000000)
        self.assertEqual(header[4:36], bytes(32), "prevhash in internal order")
        self.assertEqual(header[36:68],
                         tpl.merkle_root_for(b"\x01\x02\x03\x04")[0])
        self.assertEqual(int.from_bytes(header[68:72], "little"), 1231006505)
        self.assertEqual(int.from_bytes(header[72:76], "little"), EASY_BITS)
        self.assertEqual(int.from_bytes(header[76:80], "little"), 0xDEADBEEF)

    def test_stratum_handshake_and_job_delivery(self):
        bridge = self.start_bridge()
        self.assertTrue(self.wait_for(lambda: bridge.current_job))
        f, rpc = self.connect(bridge)

        # The bridge must push a job and a difficulty without being asked.
        got_notify = False
        got_diff = False
        import time
        deadline = time.time() + 5
        while time.time() < deadline and not (got_notify and got_diff):
            line = f.readline()
            self.assertTrue(line, "no job pushed to the miner")
            msg = json.loads(line)
            if msg.get("method") == "mining.notify":
                got_notify = True
                job_id, prev, merkle, ver, curtime, bits = msg["params"]
                self.assertEqual(job_id, bridge.current_job_id)
                self.assertEqual(prev, bridge.current_job["template"].previousblockhash)
                # Stratum carries the merkle root in display order, i.e. the
                # reverse of the internal order the header needs.
                self.assertEqual(bytes.fromhex(merkle)[::-1],
                                 bridge.current_job["merkle_root"])
                self.assertEqual(int(ver, 16), 0x20000000)
                self.assertEqual(int(curtime, 16), 1231006505)
                self.assertEqual(int(bits, 16), EASY_BITS)
            elif msg.get("method") == "mining.set_difficulty":
                got_diff = True
                self.assertEqual(msg["params"][0], 0.001)
        self.assertTrue(got_notify, "never received mining.notify")
        self.assertTrue(got_diff, "never received set_difficulty")

    def test_share_with_correct_nonce_is_accepted(self):
        bridge = self.start_bridge()
        self.assertTrue(self.wait_for(lambda: bridge.current_job))
        f, rpc = self.connect(bridge)
        job_id = bridge.current_job_id
        tpl = bridge.current_job["template"]

        x2 = bridge.current_job["extranonce2_bytes"]
        # Search for a share at the share difficulty, which is the realistic
        # case: a miner hands up easy shares continuously and wins nothing.
        nonce = find_valid_nonce(tpl, x2, tpl.share_target)
        self.assertIsNotNone(nonce, "could not find a nonce clearing the share target")
        self.assertTrue(hash_below_target(block_hash(tpl.header_for(x2, nonce)),
                                          tpl.share_target))
        # Most shares are not blocks, which is exactly what solo mining is.
        self.assertFalse(hash_below_target(block_hash(tpl.header_for(x2, nonce)),
                                           tpl.target),
                         "expected an ordinary share, not a block")

        resp = rpc("mining.submit",
                   ["w", job_id, x2.hex(), "%08x" % tpl.curtime, "%08x" % nonce], 3)
        self.assertTrue(resp.get("result"), "valid share was rejected: %s" % resp)
        self.assertGreaterEqual(bridge.stats["accepted"], 1)

    def test_low_difficulty_share_is_rejected(self):
        # A share must clear the share difficulty. A hash that clears neither
        # gate has to be refused, otherwise a rig full of garbage shares looks
        # exactly like a rig doing real work.
        #
        # A share difficulty above 1 scales the share target DOWN, so shares
        # become harder than the network target and almost everything is
        # rejected. That is the degenerate case being pinned down here.
        bridge = self.start_bridge(share_diff=1e9)
        self.assertTrue(self.wait_for(lambda: bridge.current_job))
        f, rpc = self.connect(bridge)
        job_id = bridge.current_job_id
        tpl = bridge.current_job["template"]
        x2 = bridge.current_job["extranonce2_bytes"]

        # Find a nonce that clears neither gate: overwhelmingly likely to be
        # nonce 0, but search so the test is not built on that assumption.
        self.assertLess(int.from_bytes(tpl.share_target, "big"),
                        int.from_bytes(tpl.target, "big"),
                        "share_diff > 1 should make shares harder than the network")  # noqa: E501
        weak = None
        for i in range(200):
            if not hash_below_target(block_hash(tpl.header_for(x2, i)),
                                     tpl.share_target):
                weak = i
                break
        self.assertIsNotNone(weak, "expected some nonces to miss the share target")
        resp = rpc("mining.submit",
                   ["w", job_id, x2.hex(), "%08x" % tpl.curtime, "%08x" % weak], 7)
        self.assertFalse(resp.get("result"), "weak share should be rejected")
        self.assertEqual(bridge.stats["weak"], 1)
        self.assertEqual(bridge.stats["accepted"], 0)
        self.assertEqual(self.httpd.submitted, [])

    def test_share_for_an_unknown_job_is_rejected_as_stale(self):
        bridge = self.start_bridge()
        self.assertTrue(self.wait_for(lambda: bridge.current_job))
        f, rpc = self.connect(bridge)
        resp = rpc("mining.submit", ["w", "999999", "00000000", "%08x" % 1231006505,
                                    "00000001"], 4)
        self.assertFalse(resp.get("result"))
        self.assertEqual(bridge.stats["stale"], 1)
        self.assertEqual(self.httpd.submitted, [],
                         "a stale share must never trigger a block submission")

    def test_solved_block_is_submitted_verbatim(self):
        bridge = self.start_bridge()
        self.assertTrue(self.wait_for(lambda: bridge.current_job))
        f, rpc = self.connect(bridge)
        job_id = bridge.current_job_id
        tpl = bridge.current_job["template"]
        x2 = bridge.current_job["extranonce2_bytes"]

        nonce = find_valid_nonce(tpl, x2)
        self.assertIsNotNone(nonce)

        before = len(self.httpd.submitted)
        rpc("mining.submit",
            ["w", job_id, x2.hex(), "%08x" % tpl.curtime, "%08x" % nonce], 5)
        self.assertEqual(len(self.httpd.submitted), before + 1,
                         "a block under target was not submitted")

        submitted = bytes.fromhex(self.httpd.submitted[-1])
        # The submitted blob must be a well formed block whose header hashes to
        # what the share claimed, or the network would reject it.
        header, rest = submitted[:80], submitted[80:]
        self.assertEqual(header, tpl.header_for(x2, nonce))
        self.assertTrue(hash_below_target(block_hash(header), tpl.target))
        self.assertEqual(rest[0], 2, "block should hold coinbase plus one tx")
        self.assertEqual(bridge.stats["blocks"], 1)

    def test_payout_address_cannot_be_set_by_the_miner(self):
        # The stratum username is ignored for payout. A miner pointed at this
        # bridge with someone else's address must not redirect the reward.
        bridge = self.start_bridge()
        self.assertTrue(self.wait_for(lambda: bridge.current_job))
        f, rpc = self.connect(bridge)
        rpc("mining.authorize",
            ["1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2", "x"], 6)
        self.assertEqual(bridge.address, TEST_ADDRESS,
                         "bridge must pay its configured address only")
        self.assertEqual(bridge.current_job["template"].address, TEST_ADDRESS)

    def test_bridge_refuses_an_address_from_the_wrong_chain(self):
        # A valid LTC address must not be accepted as a BTC payout.
        with self.assertRaises(AddressError):
            address_to_script("MQ3qudKtDzSmwg7tHUV7JZTXizLYBtzffj",
                              solo_bridge.CHAINS["btc"].b58_versions)
        # And the invalid DOGE address recorded in the repo README must fail.
        with self.assertRaises(AddressError):
            address_to_script("Dai6AHB6D4M152PWjnHNFF8v",
                              solo_bridge.CHAINS["doge"].b58_versions)

    def test_daemon_rpc_auth_is_sent(self):
        daemon = solo_bridge.Daemon(host="127.0.0.1", port=self.rpc_port,
                                    user="rpcuser", password="rpcpass")
        daemon.getblockchaininfo()
        import base64
        expected = base64.b64encode(b"rpcuser:rpcpass").decode()
        self.assertEqual(self.httpd.auth_seen, "Basic " + expected)

    def test_config_check_rejects_an_invalid_address(self):
        import tempfile
        cfg = {"chain": "doge", "address": "Dai6AHB6D4M152PWjnHNFF8v",
               "rpcuser": "u", "rpcpassword": "p", "rpcport": self.rpc_port}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(cfg, fh)
            path = fh.name
        # argparse writes its own error to stderr; silence it so a passing run
        # does not look like a failure in the log.
        import contextlib
        import io
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                with self.assertRaises(SystemExit):
                    solo_bridge.main(["-c", path, "--check"])
            self.assertIn("payout address rejected", err.getvalue())
            # The message must name the file to fix and the chain, so the
            # operator is not left guessing which of four configs is wrong.
            self.assertIn(path, err.getvalue())
            self.assertIn("DOGE", err.getvalue())
        finally:
            os.unlink(path)


class TestShippedConfigs(unittest.TestCase):
    """The configs in this repo must match what the installer and chain table
    claim. A config that drifts from the code is how a rig ends up paying an
    address for the wrong chain."""

    CONFIG_DIR = os.path.join(HERE, "configs")

    def shipped_raw(self, coin):
        """Read a shipped config as text."""
        with open(os.path.join(self.CONFIG_DIR, coin + ".json"),
                  encoding="utf-8") as fh:
            return fh.read()

    def shipped(self, coin):
        """Read a shipped config as parsed JSON."""
        return json.loads(self.shipped_raw(coin))

    def test_all_four_coins_have_a_config(self):
        for coin in ("btc", "ltc", "doge", "rvn"):
            self.assertTrue(os.path.exists(os.path.join(self.CONFIG_DIR,
                                                        coin + ".json")),
                            "missing config for %s" % coin)

    def test_chain_and_rpc_port_match_the_chain_table(self):
        for coin in ("btc", "ltc", "doge", "rvn"):
            cfg = self.shipped(coin)
            chain = solo_bridge.CHAINS[cfg["chain"]]
            self.assertEqual(cfg["chain"], coin)
            self.assertEqual(cfg["rpcport"], chain.rpc,
                             "%s rpcport disagrees with the chain table" % coin)
            self.assertEqual(cfg["rpchost"], "127.0.0.1",
                             "%s must talk to a local daemon" % coin)

    def test_stratum_ports_are_unique_and_on_loopback(self):
        ports = {}
        for coin in ("btc", "ltc", "doge", "rvn"):
            cfg = self.shipped(coin)
            port = cfg["stratum_port"]
            self.assertNotIn(port, ports,
                             "%s and %s both want stratum port %s"
                             % (coin, ports.get(port), port))
            ports[port] = coin
            self.assertEqual(cfg["listen"], "127.0.0.1")

    def test_btc_and_ltc_addresses_are_the_ones_on_record(self):
        # Preserved verbatim from this repo's README. Changing them silently
        # would redirect a real payout.
        self.assertEqual(self.shipped("btc")["address"],
                         "33oBrFCtn7SvqULsERymwtwmM8mXSrgcd9")
        self.assertEqual(self.shipped("ltc")["address"],
                         "MQ3qudKtDzSmwg7tHUV7JZTXizLYBtzffj")

    def test_btc_and_ltc_addresses_pass_own_chain_validation(self):
        for coin in ("btc", "ltc"):
            cfg = self.shipped(coin)
            script = address_to_script(cfg["address"],
                                       solo_bridge.CHAINS[coin].b58_versions)
            self.assertEqual(len(script), 23, "%s should be P2SH" % coin)

    def test_recorded_doge_address_is_preserved_but_invalid(self):
        # Kept as recorded, deliberately, so the fact it is wrong is visible
        # rather than silently deleted.
        cfg = self.shipped("doge")
        self.assertEqual(cfg["address"], "Dai6AHB6D4M152PWjnHNFF8v")
        with self.assertRaises(AddressError):
            address_to_script(cfg["address"],
                              solo_bridge.CHAINS["doge"].b58_versions)

    def test_rvn_address_is_a_placeholder_not_an_invented_one(self):
        cfg = self.shipped("rvn")
        self.assertTrue(cfg["address"].startswith("REPLACE_"),
                        "an RVN address must never be invented")
        with self.assertRaises(AddressError):
            address_to_script(cfg["address"],
                              solo_bridge.CHAINS["rvn"].b58_versions)

    def test_no_config_points_at_a_pool(self):
        # Match actual endpoints, not the word "pool": these files explain in
        # prose that they are NOT a pool, which is the point of the comments.
        for coin in ("btc", "ltc", "doge", "rvn"):
            raw = self.shipped_raw(coin)
            for marker in ("viabtc", "zpool", "ckpool", "stratum+tcp://",
                           "nicehash", "pool.mine", ".pool.", "pool_url",
                           "upstream"):
                self.assertNotIn(marker, raw,
                                 "%s config mentions %r" % (coin, marker))
            # The only stratum host configured must be loopback.
            self.assertNotRegex(raw, r"stratum\+tcp://(?!127\.0\.0\.1)")

    def test_share_difficulty_is_in_a_sane_range(self):
        for coin in ("btc", "ltc", "doge", "rvn"):
            d = self.shipped(coin)["share_diff"]
            # Below 1 means easy shares, which is what stratum metering wants.
            # Far below 1e-6 would make the share target unspendably large.
            self.assertGreater(d, 1e-6, "%s share_diff is too small" % coin)
            self.assertLessEqual(d, 1.0, "%s share_diff should be <= 1" % coin)


if __name__ == "__main__":
    unittest.main(verbosity=2)
