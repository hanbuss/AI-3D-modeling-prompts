"""mk18/lib/png.py — 最小 PNG 读写（8bit RGB，无第三方依赖）
绕开 bpy 的 image.pixels 缓冲在某些版本上 foreach_set 丢数据的问题。
"""
import zlib, struct
import numpy as np


def write_png(path, rgb8):
    h, w, _ = rgb8.shape
    zero = bytes(1)
    buf = bytearray()
    for y in range(h):
        buf += zero
        buf += rgb8[y].tobytes()

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]))
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(bytes(buf), 9)))
        f.write(chunk(b"IEND", b""))


def read_png(path):
    """读回 8bit RGB PNG（仅支持我们的 writer 产出的 filter=0 行）"""
    data = open(path, 'rb').read()
    assert data[:8] == bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
    off = 8
    w = h = None
    idat = bytearray()
    while off < len(data):
        ln = struct.unpack(">I", data[off:off + 4])[0]
        tag = data[off + 4:off + 8]
        payload = data[off + 8:off + 8 + ln]
        if tag == b"IHDR":
            w, h, bd, ct = struct.unpack(">IIBB", payload[:10])
        elif tag == b"IDAT":
            idat += payload
        off += 12 + ln
    raw = zlib.decompress(bytes(idat))
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, 1 + w * 3)[:, 1:].reshape(h, w, 3)
    return arr
