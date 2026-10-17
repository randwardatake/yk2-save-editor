#!/usr/bin/env python3
"""Save editor for Yakuza Kiwami 2 (2025 remaster, yakuzakiwami2_r.exe).

data.sav layout: JSON XOR'd with the repeating key "STarYZgr3DL11",
followed by CRC32 of the plain JSON (4 bytes, little-endian, not encrypted).

Edits are done in place on the raw JSON bytes (the file is never
re-serialized), so the game's own number formatting is preserved.
A timestamped backup is written before every change.
"""
import argparse
import json
import os
import re
import shutil
import struct
import sys
import time
import zlib

KEY = b"STarYZgr3DL11"
BACKUP_DIR = os.environ.get(
    "YK2SAVE_BACKUP_DIR", os.path.expanduser("~/.local/share/yk2save/backups")
)


def xor(data):
    return bytes(c ^ KEY[i % len(KEY)] for i, c in enumerate(data))


def load(path):
    raw = open(path, "rb").read()
    body = xor(raw[:-4])
    if struct.unpack("<I", raw[-4:])[0] != zlib.crc32(body):
        sys.exit(f"{path}: CRC mismatch, not a Yakuza Kiwami 2 save")
    return body


def store(path, body):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    slot = os.path.basename(os.path.dirname(os.path.abspath(path)))
    backup = os.path.join(BACKUP_DIR, f"{slot}-{time.strftime('%Y%m%d-%H%M%S')}.sav")
    shutil.copy2(path, backup)
    with open(path, "wb") as f:
        f.write(xor(body) + struct.pack("<I", zlib.crc32(body)))
    load(path)  # verify round-trip
    print(f"backup: {backup}")


def summary(body):
    j = json.loads(body)
    base = j["base"]
    return {
        "title": base["m_subtitle"].strip(),
        "detail": base["m_detail"].replace("\n", "  "),
        "money": j["player"]["point"]["m_point"][1],
    }


def cmd_info(args):
    for path in args.saves:
        s = summary(load(path))
        print(f"{path}\n  {s['title']}\n  {s['detail']}\n  money: {s['money']:,}")


def cmd_money(args):
    body = load(args.save)
    old = json.loads(body)["player"]["point"]["m_point"][1]
    pattern = re.compile(rb'("m_point":\[\d+,)%d([,\]])' % old)
    if len(pattern.findall(body)) != 1:
        sys.exit("money field not found uniquely, refusing to edit")
    body = pattern.sub(rb"\g<1>%d\g<2>" % args.yen, body)
    body = re.sub(
        rb"\[Mny\] \xc2\xa5[\d,]+", "[Mny] ¥{:,}".format(args.yen).encode(), body, count=1
    )
    store(args.save, body)
    print(f"money: {old:,} -> {args.yen:,}")


def cmd_decrypt(args):
    body = load(args.save)
    with open(args.out, "wb") as f:
        f.write(body)
    print(f"wrote {args.out}")


def cmd_encrypt(args):
    body = open(args.json, "rb").read()
    json.loads(body)  # must be valid JSON
    if os.path.exists(args.save):
        store(args.save, body)
    else:
        with open(args.save, "wb") as f:
            f.write(xor(body) + struct.pack("<I", zlib.crc32(body)))
    print(f"wrote {args.save}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("info", help="show chapter, play time and money")
    s.add_argument("saves", nargs="+")
    s.set_defaults(func=cmd_info)

    s = sub.add_parser("money", help="set money (yen)")
    s.add_argument("save")
    s.add_argument("yen", type=int)
    s.set_defaults(func=cmd_money)

    s = sub.add_parser("decrypt", help="dump plain JSON for manual editing")
    s.add_argument("save")
    s.add_argument("out")
    s.set_defaults(func=cmd_decrypt)

    s = sub.add_parser("encrypt", help="write plain JSON back as a save")
    s.add_argument("json")
    s.add_argument("save")
    s.set_defaults(func=cmd_encrypt)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
