#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 app.ico —— 纯标准库，无需 Pillow"""
import struct


def _lerp(a, b, t):
    return a + (b - a) * t


def _round_rect(x, y, r):
    """单位坐标下，边距 r 的圆角矩形判定"""
    if x < 0 or x > 1 or y < 0 or y > 1:
        return False
    cx = min(max(x, r), 1 - r)
    cy = min(max(y, r), 1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r or (r <= x <= 1 - r) or (r <= y <= 1 - r)


def _arrow_right(x, y):
    # 横杆
    if 0.20 <= x <= 0.60 and 0.365 <= y <= 0.455:
        return True
    # 箭头
    if 0.60 <= x <= 0.79:
        hh = 0.133 * (1 - (x - 0.60) / 0.19)
        return abs(y - 0.41) <= hh
    return False


def _arrow_left(x, y):
    if 0.40 <= x <= 0.80 and 0.545 <= y <= 0.635:
        return True
    if 0.21 <= x <= 0.40:
        hh = 0.133 * (1 - (0.40 - x) / 0.19)
        return abs(y - 0.59) <= hh
    return False


def render(size, ss=3):
    W = size * ss
    buf = []
    for j in range(W):
        y = (j + 0.5) / W
        for i in range(W):
            x = (i + 0.5) / W
            if not _round_rect(x, y, 0.24):
                buf.append((0, 0, 0, 0))
            elif _arrow_right(x, y) or _arrow_left(x, y):
                buf.append((255, 255, 255, 255))
            else:
                t = y
                buf.append((int(_lerp(59, 37, t)), int(_lerp(130, 99, t)), int(_lerp(246, 235, t)), 255))

    # 盒式降采样
    out = bytearray()
    for j in range(size):
        for i in range(size):
            r = g = b = a = n = 0
            for dj in range(ss):
                for di in range(ss):
                    pr, pg, pb, pa = buf[(j * ss + dj) * W + (i * ss + di)]
                    r += pr * pa
                    g += pg * pa
                    b += pb * pa
                    a += pa
                    n += 1
            if a == 0:
                out += bytes((0, 0, 0, 0))
            else:
                out += bytes((r // a, g // a, b // a, a // n))
    return bytes(out)


def make_ico(path, sizes=(16, 24, 32, 48, 64, 128, 256)):
    images = []
    for s in sizes:
        rgba = render(s)
        # ICO 里的 32 位 BMP 是 BGRA 顺序，需要把 R/B 对调
        bgra = bytearray(len(rgba))
        bgra[0::4] = rgba[2::4]
        bgra[1::4] = rgba[1::4]
        bgra[2::4] = rgba[0::4]
        bgra[3::4] = rgba[3::4]
        pixels = bytes(bgra)
        header = struct.pack("<IiiHHIIiiII", 40, s, s * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0)
        # AND 掩码：32 位图靠 alpha，掩码全 0，每行补齐到 4 字节
        row = ((s + 31) // 32) * 4
        mask = bytes(row * s)
        images.append((s, header + pixels + mask))

    data = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    offset = 6 + 16 * len(images)
    for s, blob in images:
        bw = 0 if s >= 256 else s
        data += struct.pack("<BBBBHHII", bw, bw, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    for _, blob in images:
        data += blob
    with open(path, "wb") as f:
        f.write(bytes(data))
    return path


if __name__ == "__main__":
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    p = make_ico(os.path.join(here, "app.ico"))
    print("已生成", p, os.path.getsize(p), "字节")
