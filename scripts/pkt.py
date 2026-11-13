#!/usr/bin/env python3
"""Pure-python Twofish + EAX and Packet Tracer .pkt encode/decode (pka2xml scheme)."""
import sys, zlib, struct

def _q(t):
    def ror4(x, n): return ((x >> n) | (x << (4 - n))) & 0xF
    out = []
    for x in range(256):
        a0, b0 = x >> 4, x & 15
        a1 = a0 ^ b0; b1 = a0 ^ ror4(b0, 1) ^ ((8 * a0) & 15)
        a2, b2 = t[0][a1], t[1][b1]
        a3 = a2 ^ b2; b3 = a2 ^ ror4(b2, 1) ^ ((8 * a2) & 15)
        a4, b4 = t[2][a3], t[3][b3]
        out.append(16 * b4 + a4)
    return out

Q0 = _q([[0x8,0x1,0x7,0xD,0x6,0xF,0x3,0x2,0x0,0xB,0x5,0x9,0xE,0xC,0xA,0x4],
         [0xE,0xC,0xB,0x8,0x1,0x2,0x3,0x5,0xF,0x4,0xA,0x6,0x7,0x0,0x9,0xD],
         [0xB,0xA,0x5,0xE,0x6,0xD,0x9,0x0,0xC,0x8,0xF,0x3,0x2,0x4,0x7,0x1],
         [0xD,0x7,0xF,0x4,0x1,0x2,0x6,0xE,0x9,0xB,0x3,0x0,0x8,0x5,0xC,0xA]])
Q1 = _q([[0x2,0x8,0xB,0xD,0xF,0x7,0x6,0xE,0x3,0x1,0x9,0x4,0x0,0xA,0xC,0x5],
         [0x1,0xE,0x2,0xB,0x4,0xC,0x3,0x7,0x6,0xD,0xA,0x5,0xF,0x9,0x0,0x8],
         [0x4,0xC,0x7,0x5,0x1,0x6,0x9,0xA,0x0,0xE,0xD,0x8,0x2,0xB,0x3,0xF],
         [0xB,0x9,0x5,0x1,0xC,0x3,0xD,0xE,0x6,0x4,0x7,0xF,0x2,0x0,0x8,0xA]])

def gmul(a, b, poly):
    r = 0
    while b:
        if b & 1: r ^= a
        a <<= 1
        if a & 0x100: a ^= poly
        b >>= 1
    return r

MDS = [[0x01,0xEF,0x5B,0x5B],[0x5B,0xEF,0xEF,0x01],[0xEF,0x5B,0x01,0xEF],[0xEF,0x01,0xEF,0x5B]]
RS = [[0x01,0xA4,0x55,0x87,0x5A,0x58,0xDB,0x9E],[0xA4,0x56,0x82,0xF3,0x1E,0xC6,0x68,0xE5],
      [0x02,0xA1,0xFC,0xC1,0x47,0xAE,0x3D,0x19],[0xA4,0x55,0x87,0x5A,0x58,0xDB,0x9E,0x03]]
M32 = 0xFFFFFFFF
def rol(x, n): return ((x << n) | (x >> (32 - n))) & M32
def ror(x, n): return ((x >> n) | (x << (32 - n))) & M32
def b4(w): return [(w >> (8 * i)) & 255 for i in range(4)]
def w4(b): return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)

def h(X, L):
    y = b4(X); k = len(L); Lb = [b4(l) for l in L]
    if k == 4:
        y = [Q1[y[0]] ^ Lb[3][0], Q0[y[1]] ^ Lb[3][1], Q0[y[2]] ^ Lb[3][2], Q1[y[3]] ^ Lb[3][3]]
    if k >= 3:
        y = [Q1[y[0]] ^ Lb[2][0], Q1[y[1]] ^ Lb[2][1], Q0[y[2]] ^ Lb[2][2], Q0[y[3]] ^ Lb[2][3]]
    y = [Q1[Q0[Q0[y[0]] ^ Lb[1][0]] ^ Lb[0][0]],
         Q0[Q0[Q1[y[1]] ^ Lb[1][1]] ^ Lb[0][1]],
         Q1[Q1[Q0[y[2]] ^ Lb[1][2]] ^ Lb[0][2]],
         Q0[Q1[Q1[y[3]] ^ Lb[1][3]] ^ Lb[0][3]]]
    z = [0] * 4
    for i in range(4):
        for j in range(4):
            z[i] ^= gmul(MDS[i][j], y[j], 0x169)
    return w4(z)

class Twofish:
    def __init__(self, key):
        k = len(key) // 8
        M = [w4(list(key[4*i:4*i+4])) for i in range(2*k)]
        Me = [M[2*i] for i in range(k)]; Mo = [M[2*i+1] for i in range(k)]
        S = []
        for i in range(k):
            m = list(key[8*i:8*i+8]); s = [0]*4
            for r in range(4):
                for c in range(8):
                    s[r] ^= gmul(RS[r][c], m[c], 0x14D)
            S.append(w4(s))
        self.S = S[::-1]
        rho = 0x01010101; self.K = []
        for i in range(20):
            A = h((2*i*rho) & M32, Me); B = rol(h(((2*i+1)*rho) & M32, Mo), 8)
            self.K.append((A + B) & M32); self.K.append(rol((A + 2*B) & M32, 9))
        # precompute g via full h each time (slow but fine) -> cache per-byte tables
        Lb = [b4(l) for l in self.S]
        chains = [lambda y: Q1[Q0[Q0[y] ^ Lb[1][0]] ^ Lb[0][0]],
                  lambda y: Q0[Q0[Q1[y] ^ Lb[1][1]] ^ Lb[0][1]],
                  lambda y: Q1[Q1[Q0[y] ^ Lb[1][2]] ^ Lb[0][2]],
                  lambda y: Q0[Q1[Q1[y] ^ Lb[1][3]] ^ Lb[0][3]]]
        self.T = []
        for pos in range(4):
            tab = []
            for x in range(256):
                yv = chains[pos](x)
                tab.append(w4([gmul(MDS[i][pos], yv, 0x169) for i in range(4)]))
            self.T.append(tab)
    def g(self, X):
        return self.T[0][X & 255] ^ self.T[1][(X >> 8) & 255] ^ self.T[2][(X >> 16) & 255] ^ self.T[3][X >> 24]
    def encrypt(self, blk):
        K = self.K
        R = [w4(list(blk[4*i:4*i+4])) ^ K[i] for i in range(4)]
        for r in range(16):
            T0 = self.g(R[0]); T1 = self.g(rol(R[1], 8))
            F0 = (T0 + T1 + K[2*r+8]) & M32; F1 = (T0 + 2*T1 + K[2*r+9]) & M32
            R2 = ror(R[2] ^ F0, 1); R3 = rol(R[3], 1) ^ F1
            R = [R2, R3, R[0], R[1]]
        R = [R[2], R[3], R[0], R[1]]
        out = b''
        for i in range(4): out += bytes(b4(R[i] ^ K[i+4]))
        return out

def _dbl(b):
    n = int.from_bytes(b, 'big') << 1
    if n >> 128: n = (n & ((1 << 128) - 1)) ^ 0x87
    return n.to_bytes(16, 'big')

def cmac(c, data):
    L = c.encrypt(bytes(16)); K1 = _dbl(L); K2 = _dbl(K1)
    if len(data) and len(data) % 16 == 0:
        blocks = [data[i:i+16] for i in range(0, len(data), 16)]
        last = bytes(a ^ b for a, b in zip(blocks[-1], K1))
    else:
        blocks = [data[i:i+16] for i in range(0, len(data), 16)] or [b'']
        pad = blocks[-1] + b'\x80' + bytes(15 - len(blocks[-1]))
        last = bytes(a ^ b for a, b in zip(pad, K2))
    x = bytes(16)
    for blk in blocks[:-1]:
        x = c.encrypt(bytes(a ^ b for a, b in zip(x, blk)))
    return c.encrypt(bytes(a ^ b for a, b in zip(x, last)))

def omac(c, t, data): return cmac(c, bytes(15) + bytes([t]) + data)

def ctr(c, iv, data):
    n = int.from_bytes(iv, 'big'); out = bytearray()
    for i in range(0, len(data), 16):
        ks = c.encrypt(n.to_bytes(16, 'big')); n = (n + 1) % (1 << 128)
        out += bytes(a ^ b for a, b in zip(data[i:i+16], ks))
    return bytes(out)

def eax_decrypt(c, nonce, ct):
    N = omac(c, 0, nonce); return ctr(c, N, ct)
def eax_encrypt(c, nonce, pt):
    N = omac(c, 0, nonce); H = omac(c, 1, b''); ct = ctr(c, N, pt); C = omac(c, 2, ct)
    tag = bytes(a ^ b ^ d for a, b, d in zip(N, H, C)); return ct + tag

KEY = bytes([137]) * 16; IV = bytes([16]) * 16
_C = None
def cipher():
    global _C
    if _C is None: _C = Twofish(KEY)
    return _C

def decode(raw):
    n = len(raw)
    s1 = bytes((raw[n - 1 - i] ^ ((n - i * n) & 0xFF)) for i in range(n))
    dec = eax_decrypt(cipher(), IV, s1[:-16])
    m = len(dec)
    s3 = bytes((dec[i] ^ ((m - i) & 0xFF)) for i in range(m))
    return zlib.decompress(s3[4:])

def encode(xml):
    comp = struct.pack('>I', len(xml)) + zlib.compress(xml)
    m = len(comp)
    s3 = bytes((comp[i] ^ ((m - i) & 0xFF)) for i in range(m))
    enc = eax_encrypt(cipher(), IV, s3)
    n = len(enc)
    out = bytearray(n)
    for i in range(n):
        out[n - 1 - i] = enc[i] ^ ((n - i * n) & 0xFF)
    return bytes(out)

if __name__ == '__main__':
    if sys.argv[1] == 'test':
        print(hex(Q0[0]), hex(Q1[0]))
        print(Twofish(bytes(16)).encrypt(bytes(16)).hex().upper())
    elif sys.argv[1] == 'd':
        open(sys.argv[3], 'wb').write(decode(open(sys.argv[2], 'rb').read()))
    elif sys.argv[1] == 'e':
        open(sys.argv[3], 'wb').write(encode(open(sys.argv[2], 'rb').read()))
