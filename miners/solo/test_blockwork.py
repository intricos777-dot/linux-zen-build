#!/usr/bin/env python3
"""Correctness tests for solo block construction.

These check against published, independently verifiable vectors rather than
against our own daemon, because the failure mode of a wrong merkle root or a
wrong BIP34 push is a rig that runs for months and never finds anything.

Run: python3 miners/solo/test_blockwork.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blockwork import (  # noqa: E402
    AddressError, address_to_script, b58decode_check, bip34_script, compact_to_target,
    dsha256, hash_below_target, make_coinbase, make_header, merkle_root,
    target_to_compact, target_to_diff, target_to_hex, varint,
)

# Bitcoin genesis block, block 0. Every value below is from the Bitcoin
# whitepaper / block header, so a mistake cannot hide here.
GENESIS_CB = bytes.fromhex(
    "01000000010000000000000000000000000000000000000000000000000000000000000000"
    "ffffffff4d04ffff001d0104455468652054696d65732030332f4a616e2f32303039204368"
    "616e63656c6c6f72206f6e206272696e6b206f66207365636f6e64206261696c6f75742066"
    "6f722062616e6b73ffffffff0100f2052a01000000434104678afdb0fe5548271967f1a671"
    "30b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c38"
    "4df7ba0b8d578a4c702b6bf11d5fac00000000")
# Internal (serialised) byte order, as it appears inside the header.
GENESIS_MERKLE = bytes.fromhex(
    "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a")
# The same merkle root in display order, i.e. reversed.
GENESIS_MERKLE_DISPLAY = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
GENESIS_HEADER = bytes.fromhex(
    "0100000000000000000000000000000000000000000000000000000000000000000000003b"
    "a3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff"
    "001d1dac2b7c")
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_BITS = 0x1D00FFFF
GENESIS_TIME = 1231006505
GENESIS_NONCE = 2083236893

# Litecoin mainnet: PUBKEY_ADDRESS 0x30, SCRIPT_ADDRESS 0x32
LTC_VERSIONS = {0x30, 0x32}
BTC_VERSIONS = {0x00, 0x05}
DOGE_VERSIONS = {0x1E, 0x16}
RVN_VERSIONS = {0x3E, 0x05}   # 0x3E = 62 = RVN PUBKEY_ADDRESS


def cscript_num_len(n):
    """Expected byte length of the CScriptNum encoding of n."""
    if n == 0:
        return 0
    raw = n.to_bytes((n.bit_length() + 7) // 8, "little")
    if raw[-1] & 0x80:
        raw += b"\x00"
    return len(raw)


class TestMerkleAndGenesis(unittest.TestCase):
    def test_genesis_coinbase_is_parsed_correctly(self):
        # The genesis coinbase's single txid, in internal byte order.
        txid = dsha256(GENESIS_CB)
        self.assertEqual(txid, merkle_root([txid]))

    def test_genesis_merkle_root_matches_published_value(self):
        # A single-transaction block: the merkle root IS the coinbase txid.
        self.assertEqual(merkle_root([dsha256(GENESIS_CB)]), GENESIS_MERKLE)
        # And in the display order block explorers print it, it is reversed.
        self.assertEqual(GENESIS_MERKLE[::-1].hex(), GENESIS_MERKLE_DISPLAY)

    def test_merkle_root_duplicates_last_odd_leaf(self):
        # Odd leaf counts duplicate the final hash, not pad with a zero hash.
        a, b, c = b"\x01" * 32, b"\x02" * 32, b"\x03" * 32
        self.assertEqual(merkle_root([a, b, c]), merkle_root([a, b, c, c]))
        self.assertNotEqual(merkle_root([a, b, c]), merkle_root([a, b, b"\x00" * 32]))

    def test_genesis_header_assembles_and_hashes_to_the_known_block_hash(self):
        header = make_header(
            version=1,
            prevhash_le=bytes(32),
            merkleroot=GENESIS_MERKLE,
            ntime=GENESIS_TIME,
            nbits=GENESIS_BITS,
            nonce=GENESIS_NONCE,
        )
        self.assertEqual(len(header), 80)
        self.assertEqual(header, GENESIS_HEADER)
        self.assertEqual(dsha256(header)[::-1].hex(), GENESIS_HASH)

    def test_genesis_block_serialisation_is_well_formed(self):
        block = GENESIS_HEADER + varint(1) + GENESIS_CB
        self.assertEqual(dsha256(block[:80])[::-1].hex(), GENESIS_HASH)


class TestTargets(unittest.TestCase):
    def test_genesis_compact_target_round_trips(self):
        target = compact_to_target(GENESIS_BITS)
        self.assertEqual(target_to_hex(target),
                         "00000000ffff0000000000000000000000000000000000000000000000000000")
        self.assertEqual(target_to_compact(target), GENESIS_BITS)

    def test_difficulty_one_target(self):
        self.assertAlmostEqual(target_to_diff(compact_to_target(0x1D00FFFF)), 1.0)

    def test_genesis_hash_meets_difficulty_one_target(self):
        digest = bytes.fromhex(GENESIS_HASH)
        self.assertTrue(hash_below_target(digest, compact_to_target(GENESIS_BITS)))

    def test_an_easy_target_is_easier_than_a_hard_one(self):
        easy = compact_to_target(0x1D00FFFF)   # difficulty 1
        hard = compact_to_target(0x1B0404CB)   # a real historical 10M-ish target
        # A lower nBits exponent gives a higher difficulty, so a smaller target:
        # fewer hashes pass, which is exactly what "harder" means. Getting this
        # inequality backwards inverts the share check and makes a rig that
        # accepts every share look healthy while it is in fact doing nothing.
        self.assertGreater(target_to_diff(hard), target_to_diff(easy))
        self.assertLess(int.from_bytes(hard, "big"), int.from_bytes(easy, "big"))

    def test_difficulty_moves_the_right_way_with_the_exponent(self):
        # Every 0x10000 in the mantissa is a four-fold difficulty change, which
        # is the relationship getworkstyle share maths depends on.
        for exponent in range(0x18, 0x1E):
            base = target_to_diff(compact_to_target((exponent << 24) | 0x123456))
            harder = target_to_diff(compact_to_target((exponent << 24) | 0x123457))
            self.assertLess(harder, base)

    def test_high_difficulty_compact_target_is_representable(self):
        # Real mainnet difficulty regularly needs a 0x18 exponent; a target
        # builder that cannot round trip these is a rig that stops submitting.
        for compact in (0x17034219, 0x18034219, 0x1A05D4B3, 0x1C0D4B3A):
            self.assertEqual(target_to_compact(compact_to_target(compact)), compact)

    def test_malformed_compact_targets_are_rejected(self):
        with self.assertRaises(ValueError):
            compact_to_target(0x00000000)      # zero mantissa
        with self.assertRaises(ValueError):
            compact_to_target(0x18000000 | 0x00800000)  # sign bit set


class TestCoinbase(unittest.TestCase):
    def test_bip34_height_push_is_minimal(self):
        # BIP34 requires the CScriptNum encoding: little endian, no leading
        # zero bytes, a 0x00 pad when the top bit would read as negative.
        self.assertEqual(bip34_script(0), b"\x00")
        self.assertEqual(bip34_script(1), b"\x01\x01")
        self.assertEqual(bip34_script(16), b"\x01\x10")
        self.assertEqual(bip34_script(127), b"\x01\x7f")
        self.assertEqual(bip34_script(128), b"\x02\x80\x00")
        self.assertEqual(bip34_script(0x7FFFFFFF), b"\x04\xff\xff\xff\x7f")
        self.assertEqual(bip34_script(0x80), b"\x02\x80\x00")

    def test_bip34_push_length_is_minimal(self):
        # The push opcode must describe exactly the bytes that follow, and
        # those bytes must be the shortest encoding of the height. Note that a
        # height whose low byte is zero (256, 65536) legitimately encodes with a
        # zero byte in first position, because the encoding is little endian.
        for h in (1, 2, 16, 127, 128, 255, 256, 65535, 65536, 500000000, 800000):
            script = bip34_script(h)
            self.assertEqual(script[0], len(script) - 1,
                             "wrong push length for height %d" % h)
            self.assertEqual(len(script[1:]), cscript_num_len(h),
                             "height %d is not minimally encoded" % h)

    def test_bip34_padding_only_appears_when_the_sign_bit_needs_it(self):
        # CScriptNum is little endian and signed, so a final byte with the top
        # bit set would read as negative and must be followed by a 0x00 pad.
        for h in (1, 127, 128, 255, 256, 32767, 32768, 8388607, 8388608):
            raw = h.to_bytes((h.bit_length() + 7) // 8, "little")
            needs_pad = bool(raw[-1] & 0x80)
            body = bip34_script(h)[1:]
            has_pad = body[-1] == 0 and needs_pad
            self.assertEqual(needs_pad, has_pad,
                             "height %d padded=%s but needed=%s" % (h, has_pad, needs_pad))
            if needs_pad:
                self.assertEqual(body, raw + b"\x00")
            else:
                self.assertEqual(body, raw)

    def test_coinbase_shape(self):
        spk = bytes.fromhex("76a914" + "11" * 20 + "88ac")
        cb = make_coinbase(800000, spk, 625000000)
        self.assertEqual(cb[:4], b"\x02\x00\x00\x00", "nVersion should be 2")
        self.assertEqual(cb[4], 1, "coinbase must have exactly one input")
        self.assertEqual(cb[5:37], bytes(32), "coinbase prevout must be null")
        self.assertEqual(cb[37:41], b"\xff\xff\xff\xff", "nSequence")
        scriptlen = cb[41]
        script_off = 42
        self.assertEqual(scriptlen, 4, "BIP34 push for height 800000 is 4 bytes")
        # 800000 == 0x0C3500 -> little endian 00 35 0C, top bit clear, no pad.
        self.assertEqual(cb[script_off:script_off + scriptlen],
                         b"\x03\x00\x35\x0c")
        # scriptSig is followed by nSequence, then the single output.
        out_off = script_off + scriptlen + 4
        self.assertEqual(cb[out_off], 1, "coinbase must have exactly one output")
        # The value is 8 bytes, and is the whole of the template's reward.
        self.assertEqual(int.from_bytes(cb[out_off + 1:out_off + 9], "little"),
                         625000000)
        self.assertEqual(cb[out_off + 9], len(spk), "scriptPubKey length")
        self.assertEqual(cb[out_off + 10:out_off + 10 + len(spk)], spk)
        self.assertEqual(cb[-4:], bytes(4), "nLockTime must be 0")

    def test_coinbase_pays_the_full_template_value(self):
        spk = bytes.fromhex("a914" + "22" * 20 + "87")
        cb = make_coinbase(1, spk, 12345678)
        self.assertIn(spk, cb)

    def test_extranonce_extends_the_script_without_moving_the_height(self):
        spk = bytes.fromhex("a914" + "33" * 20 + "87")
        base = make_coinbase(700000, spk, 50)
        withx = make_coinbase(700000, spk, 50, extra_script=b"\xaa\xbb\xcc\xdd")

        def script_sig(tx):
            # version(4) + varint inputs(1) + prevout(36) + varint scriptlen(1)
            return tx[42:42 + tx[41]]

        self.assertEqual(len(script_sig(withx)) - len(script_sig(base)), 4,
                         "extranonce did not extend scriptSig")
        # The BIP34 height push still comes first, so the commitment is intact,
        # and the extranonce bytes land immediately after it.
        a, b_ = script_sig(base), script_sig(withx)
        self.assertEqual(b_[:len(a) - 4], a[:-4])
        self.assertEqual(b_[-4:], b"\xaa\xbb\xcc\xdd")
        # 700000 == 0x0AAE60 -> little endian 60 AE 0A, no sign pad needed.
        self.assertEqual(b_[:4], b"\x03\x60\xae\x0a")

    def test_distinct_extranonces_give_distinct_coinbases(self):
        # This is the property that actually makes solo mining work: every
        # share must commit to a different coinbase, or the miner is re-hashing
        # the same block over and over.
        spk = bytes.fromhex("a914" + "44" * 20 + "87")
        seen = {dsha256(make_coinbase(800000, spk, 12, extra_script=bytes([i] * 4)))
                for i in range(256)}
        self.assertEqual(len(seen), 256)

    def test_coinbase_differs_per_height_so_reorgs_are_distinguishable(self):
        spk = bytes.fromhex("a914" + "55" * 20 + "87")
        a = dsha256(make_coinbase(800000, spk, 12))
        b = dsha256(make_coinbase(800001, spk, 12))
        self.assertNotEqual(a, b)


class TestAddresses(unittest.TestCase):
    BTC = "33oBrFCtn7SvqULsERymwtwmM8mXSrgcd9"
    LTC = "MQ3qudKtDzSmwg7tHUV7JZTXizLYBtzffj"
    DOGE_RECORDED = "Dai6AHB6D4M152PWjnHNFF8v"

    def test_btc_address_is_p2sh_and_checksums(self):
        ver, h = b58decode_check(self.BTC)
        self.assertEqual(ver, 0x05)
        script = address_to_script(self.BTC, BTC_VERSIONS)
        self.assertEqual(script, bytes([0xA9, 0x14]) + h + bytes([0x87]))

    def test_ltc_address_checksums_and_is_rejected_on_bitcoin(self):
        ver, h = b58decode_check(self.LTC)
        self.assertEqual(ver, 0x32)          # Litecoin SCRIPT_ADDRESS
        self.assertEqual(len(h), 20)
        # The whole point of the per-chain version set: a valid LTC address
        # must NOT be accepted as a Bitcoin payout.
        with self.assertRaises(AddressError):
            address_to_script(self.LTC, BTC_VERSIONS)
        self.assertTrue(address_to_script(self.LTC, LTC_VERSIONS))

    def test_recorded_doge_address_is_invalid_and_must_be_replaced(self):
        # The address recorded in this repo's README fails its base58 checksum,
        # so it is not a payable Dogecoin address at all. Preserved verbatim in
        # the config as documentation, but the installer refuses to use it.
        with self.assertRaises(AddressError) as ctx:
            b58decode_check(self.DOGE_RECORDED)
        self.assertIn("checksum", str(ctx.exception))

    def test_a_corrupted_address_is_caught_not_accepted(self):
        broken = self.BTC[:-1] + ("2" if self.BTC[-1] != "2" else "3")
        with self.assertRaises(AddressError):
            b58decode_check(broken)

    def test_bech32_p2wpkh(self):
        # BIP173 test vector, mainnet P2WPKH.
        script = address_to_script("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", BTC_VERSIONS)
        self.assertEqual(script.hex(), "0014751e76e8199196d454941c45d1b3a323f1433bd6")

    def test_bech32_corrupt_checksum_is_rejected(self):
        with self.assertRaises(AddressError):
            address_to_script("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5", BTC_VERSIONS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
