# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Copyright (c) 2026 Living Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
# Licensed under Living Sin Proprietary License (LSPL-1.0)
# See LICENSE file for details.
"""Block construction primitives for local solo mining.

These are the parts that must be exactly right or the rig silently never finds
a block: transaction serialisation, the BIP34 coinbase commitment, merkle roots,
the 80-byte header, and compact-target arithmetic.

Pure functions only, no I/O, so they can be tested against published vectors
(the Bitcoin genesis block) rather than against a running daemon.
"""

import hashlib
import struct

# ---------------------------------------------------------------- hashes


def dsha256(b):
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def hash160(b):
    h = hashlib.new("ripemd160", hashlib.sha256(b).digest())
    return h.digest()


# ---------------------------------------------------------------- varints


def varint(n):
    if n < 0xFD:
        return struct.pack("<B", n)
    if n <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", n)
    if n <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", n)
    return b"\xff" + struct.pack("<Q", n)


def pushdata(b):
    """Minimal push of b, as scriptSig uses it."""
    n = len(b)
    if n < 0x4C:
        return struct.pack("<B", n) + b
    if n <= 0xFF:
        return b"\x4c" + struct.pack("<B", n) + b
    if n <= 0xFFFF:
        return b"\x4d" + struct.pack("<H", n) + b
    return b"\x4e" + struct.pack("<I", n) + b


# ---------------------------------------------------------------- BIP34


def bip34_script(height, extra=b""):
    """Coinbase scriptSig carrying the committed block height (BIP34).

    The push must be the shortest encoding of the height or a node rejects the
    block, hence the little endian, no leading zeros, CScriptNum form.
    """
    h = int(height)
    if h == 0:
        encoded = b""
    else:
        raw = h.to_bytes((h.bit_length() + 7) // 8, "little")
        if raw[-1] & 0x80:
            raw += b"\x00"
        encoded = raw
    return pushdata(encoded) + extra


# ---------------------------------------------------------------- addresses

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


class AddressError(ValueError):
    pass


def b58decode_check(s):
    n = 0
    for ch in s:
        idx = B58.find(ch)
        if idx < 0:
            raise AddressError("invalid base58 character %r" % ch)
        n = n * 58 + idx
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    raw = b"\x00" * (len(s) - len(s.lstrip("1"))) + raw
    if len(raw) < 5:
        raise AddressError("address too short")
    body, crc = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(body).digest()).digest()[:4] != crc:
        raise AddressError("checksum mismatch, address is invalid")
    return body[0], body[1:]


def _bech32_polymod(values):
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= generator[i] if ((top >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _bech32_decode(s):
    if any(ord(x) < 33 or ord(x) > 126 for x in s):
        raise AddressError("bech32 character out of range")
    if s.lower() != s and s.upper() != s:
        raise AddressError("mixed case bech32")
    s = s.lower()
    pos = s.rfind("1")
    if pos < 1 or pos + 7 > len(s) or len(s) > 90:
        raise AddressError("malformed bech32 string")
    hrp, data = s[:pos], [BECH32_CHARSET.find(x) for x in s[pos + 1:]]
    if -1 in data:
        raise AddressError("invalid bech32 character")
    chk = _bech32_polymod(_bech32_hrp_expand(hrp) + data)
    const = 1 if hrp == "bc" else 0x2BC830A3
    if chk != const:
        raise AddressError("bech32 checksum mismatch")
    return hrp, data[:-6]


def _convertbits(data, frombits, tobits, pad=True):
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            raise AddressError("invalid value in bit conversion")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (tobits - bits)) & maxv)
    return ret


def address_to_script(address, versions):
    """Convert a base58 or bech32 address into a scriptPubKey.

    `versions` is the set of base58 version bytes valid for the chain being
    mined. Refusing anything outside that set is what stops a BTC address from
    being silently paid into a Litecoin block (or a typo from being accepted).
    """
    lowered = address.lower()
    if any(lowered.startswith(p) for p in ("bc1", "tb1", "bcrt1", "ltc1", "mwc1", "rvn1")):
        _hrp, data = _bech32_decode(address)
        ver = data[0]
        prog = bytes(_convertbits(data[1:], 5, 8, False))
        if len(prog) not in (20, 32):
            raise AddressError("bad witness program length")
        if ver == 0:
            return bytes([0x00, len(prog)]) + prog
        return bytes([0x50 + ver, len(prog)]) + prog
    ver, h = b58decode_check(address)
    if ver not in versions:
        raise AddressError(
            "base58 version 0x%02x is not valid for this chain (expected one of %s)"
            % (ver, ", ".join("0x%02x" % v for v in sorted(versions))))
    if len(h) != 20:
        raise AddressError("bad hash160 length")
    if ver == 0x00:
        return bytes([0x76, 0xA9, 0x14]) + h + bytes([0x88, 0xAC])
    return bytes([0xA9, 0x14]) + h + bytes([0x87])


# ---------------------------------------------------------------- targets


def compact_to_target(bits):
    """Expand an nBits compact value into a 32 byte big endian target.

    Targets are held big endian everywhere here so that they read in the same
    order as the block hashes they are compared against. Getting this order
    wrong inverts the difficulty check and makes a rig that can never win look
    like one that is merely unlucky.
    """
    exponent = bits >> 24
    mantissa = bits & 0x007FFFFF
    if bits & 0x00800000:
        raise ValueError("negative or overflow compact target")
    if mantissa == 0:
        raise ValueError("zero compact target")
    word = mantissa << (8 * (exponent - 3))
    if word >> 256:
        raise ValueError("compact target overflows 256 bits")
    return word.to_bytes(32, "big")


def target_to_compact(target):
    """Re-pack a big endian target back into nBits, as getblocktemplate gives.

    This reproduces Bitcoin Core's arith_uint256::GetCompact, including its
    canonicalisation: the exponent is the byte length of the value, and a
    mantissa whose top bit is set is shifted down and the exponent bumped. The
    byte length is measured from the most significant non-zero byte, not from
    the end of the string, so leading zero bytes of a 32 byte target count
    towards the exponent rather than being dropped.
    """
    size = len(target)
    while size > 0 and target[32 - size] == 0:
        size -= 1
    if size == 0:
        return 0
    if size <= 3:
        compact = int.from_bytes(target[32 - size:32], "big")
    else:
        compact = int.from_bytes(target[32 - size:32 - size + 3], "big")
    if compact & 0x00800000:
        compact >>= 8
        size += 1
    return (size << 24) | compact


def target_to_hex(target):
    return target.hex()


def hex_to_target(h):
    return bytes.fromhex(h)


def block_hash(header):
    """Double-SHA256 a header and return it in DISPLAY order (big endian).

    dsha256() returns internal/serialised order, which is the reverse of the
    hash everyone quotes. Always go through this for comparisons against a
    target, or the difficulty check silently inverts and nothing is ever found.
    """
    return dsha256(header)[::-1]


def hash_below_target(digest, target):
    """Is this 32 byte big endian block hash under the 32 byte big endian target?

    Both arguments must be in display order; see block_hash().
    """
    return int.from_bytes(digest, "big") < int.from_bytes(target, "big")


def target_to_diff(target):
    """Difficulty as max_target / target, the number the RPCs report."""
    max_target = int.from_bytes(compact_to_target(0x1D00FFFF), "big")
    return max_target / int.from_bytes(target, "big")


# ---------------------------------------------------------------- merkle


def merkle_root(hashes):
    """Merkle root over a list of 32 byte txids, duplicating the last on
    odd counts as Bitcoin specifies."""
    if not hashes:
        raise ValueError("no leaves for merkle root")
    layer = list(hashes)
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [dsha256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
    return layer[0]


# ---------------------------------------------------------------- txs


def make_coinbase(height, script_pubkey, value, extra_script=b"", version=2):
    """Build a coinbase transaction paying `value` satoshis to script_pubkey."""
    script_sig = bip34_script(height, extra_script)
    tx = struct.pack("<I", version)
    tx += varint(1)
    tx += b"\x00" * 32 + b"\xff\xff\xff\xff"   # null outpoint
    tx += varint(len(script_sig)) + script_sig
    tx += struct.pack("<I", 0xFFFFFFFF)        # nSequence
    tx += varint(1)                            # one output
    tx += struct.pack("<Q", value)
    tx += varint(len(script_pubkey)) + script_pubkey
    tx += struct.pack("<I", 0)                 # nLockTime
    return tx


def serialize_block(header, txs, witness=None):
    """Serialise a full block. `witness` is None for legacy blocks."""
    out = header + varint(len(txs))
    for i, tx in enumerate(txs):
        if witness is None:
            out += tx
        else:
            out += witness[i]
    return out


def make_header(version, prevhash_le, merkleroot, ntime, nbits, nonce,
                witness_root=b"\x00" * 32):
    """Assemble the 80 byte block header.

    `prevhash_le` and `merkleroot` are the internal (little endian) byte order
    that getblocktemplate hands back. `witness_root` is only serialised into
    the header for witness-aware coins and is ignored otherwise.
    """
    assert len(prevhash_le) == 32 and len(merkleroot) == 32
    return (struct.pack("<I", version) + prevhash_le + merkleroot
            + struct.pack("<I", ntime) + struct.pack("<I", nbits)
            + struct.pack("<I", nonce))
