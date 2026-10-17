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


def read_par_entry(par_path, name):
    """Return one decompressed file from a PARC archive (SLLZ v2 / zlib chunks)."""
    d = open(par_path, "rb").read()
    nfold, _, nfile, info = struct.unpack_from(">IIII", d, 0x10)
    names = [d[0x20 + i * 0x40:0x60 + i * 0x40].split(b"\0")[0].decode() for i in range(nfold + nfile)]
    i = names[nfold:].index(name)
    _, usize, csize, off, _, offhi = struct.unpack_from(">IIIIII", d, info + i * 0x20)
    b = d[off | offhi << 32:][:csize]
    if b[:4] != b"SLLZ":
        return b
    if b[5] != 2:
        sys.exit(f"{name}: unsupported SLLZ version {b[5]}")
    end = "<" if b[4] == 0 else ">"
    p = struct.unpack_from(end + "H", b, 6)[0]
    out = bytearray()
    while len(out) < usize:
        chunk = int.from_bytes(b[p:p + 3], "big")
        data = b[p + 5:p + chunk]
        try:
            out += zlib.decompress(data, -15)  # raw deflate
        except zlib.error:
            out += zlib.decompress(data)  # some chunks carry a zlib header
        p += chunk
    return bytes(out[:usize])


def armp_row_names(table):
    """Row names of a Dragon Engine ARMP table (row index = id)."""
    t = struct.unpack_from("<I", table, 0x10)[0]
    rows = struct.unpack_from("<i", table, t)[0]
    names_ptr = struct.unpack_from("<I", table, t + 0x10)[0]
    offs = struct.unpack_from(f"<{rows}I", table, names_ptr)
    return [table[o:table.index(b"\0", o)].decode("utf8", "replace") for o in offs]


def chapter_start(db_par, chapter):
    """First story step of a chapter and its scene_config id, read from the game's db.par."""
    timeline = read_par_entry(db_par, "timeline.bin")
    strings = [m.group().decode() for m in re.finditer(rb"[A-Za-z0-9_]{3,}", timeline)]
    configs = armp_row_names(read_par_entry(db_par, "scene_config.bin"))
    start = "START%02d" % chapter
    step_re = re.compile(r"[A-Z]+%02d_\d{4}$" % chapter)
    # STARTnn appears in several clock lists; the story one is followed by a step that has a scene config.
    for i, s in enumerate(strings[:-1]):
        step = strings[i + 1]
        if s == start and step_re.match(step) and "lexus2_" + step in configs:
            return step, configs.index("lexus2_" + step)
    sys.exit(f"chapter {chapter}: start step not found in game data")


def set_sheet(body, name, clock, trace):
    pat = re.compile(
        rb'\{"\.ver":1,"clock_trace":\[[^\]]*\],"current_clock":"[^"]*","name":"%s"\}' % name.encode()
    )
    if len(pat.findall(body)) != 1:
        sys.exit(f"timeline sheet {name} not found uniquely")
    tr = b'{".ver":1,"end_clock":"%s","start_clock":"%s"}' % (trace[1].encode(), trace[0].encode()) if trace else b""
    new = b'{".ver":1,"clock_trace":[%s],"current_clock":"%s","name":"%s"}' % (tr, clock.encode(), name.encode())
    return pat.sub(lambda _: new, body)


def cmd_chapter(args):
    step, config_id = chapter_start(os.path.join(args.game_dir, "data", "db.par"), args.chapter)
    body = load(args.save)
    for c in range(1, args.chapter):
        body = set_sheet(body, "lexus2_c%02d" % c, "END", ("START", "END"))
    body = set_sheet(body, "lexus2_c%02d" % args.chapter, "START", None)
    switch = "START%02d" % args.chapter
    body = set_sheet(body, "common_program_switch", switch, (switch, switch))
    # Boot straight into the chapter's first scene config, like the game's own chapter-start autosaves.
    scene = (
        b'"scene":{".ver":3,"m_daynight":1,"m_is_boot_config_id_only":true,"m_ppos":[0.0,0.0,0.0,0.0],'
        b'"m_prev_scene_config_id":0,"m_prev_scene_id":0,"m_return_history":[{".ver":2,"config_id":0,'
        b'"daynight":0,"pos_w":0.0,"pos_x":0.0,"pos_y":0.0,"pos_z":0.0,"scene_id":0,"stage_id":0}],'
        b'"m_scene_config_id":%d,"m_scene_id":0,"m_stage":0,"version":3}' % config_id
    )
    body, n = re.subn(rb'"scene":\{"\.ver":3,.*?"version":3\}', lambda _: scene, body, count=1)
    if n != 1:
        sys.exit("scene block not found")
    body = re.sub(rb'"m_subtitle":"[^"]*"', b'"m_subtitle":"Chapter %d start (edited)"' % args.chapter, body, count=1)
    json.loads(body)
    store(args.save, body)
    print(f"chapter {args.chapter}: boot scene config {config_id} (lexus2_{step}), switch {switch}")


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

    s = sub.add_parser("chapter", help="make the save boot at the start of a chapter")
    s.add_argument("save")
    s.add_argument("chapter", type=int, choices=range(2, 11), metavar="2-10")
    s.add_argument("--game-dir", required=True, help="folder containing data/db.par (runtime/media)")
    s.set_defaults(func=cmd_chapter)

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
