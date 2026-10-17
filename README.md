# yk2save

Save editor for **Yakuza Kiwami 2** (2025 remaster, `yakuzakiwami2_r.exe`). Python 3, no dependencies.

## Save format

```
data.sav = XOR(json, "STarYZgr3DL11") + CRC32(json)   # CRC: 4 bytes, little-endian, not encrypted
```

Saves live in `%APPDATA%\Sega\YakuzaKiwami2_R\Steam\<id>\saveNN\data.sav`
(`saveNN` = slot, `save31`+ are autosaves). On Linux/Proton it is the same path inside the Wine prefix.

## Usage

Close the game before editing.

```sh
# chapter, play time, money
./yk2save.py info save01/data.sav save31/data.sav

# set money
./yk2save.py money save01/data.sav 100000000

# manual editing: decrypt to JSON, edit, write back (CRC is recomputed)
./yk2save.py decrypt save01/data.sav save01.json
./yk2save.py encrypt save01.json save01/data.sav
```

Every write first copies the original to `~/.local/share/yk2save/backups/`
(override with `YK2SAVE_BACKUP_DIR`) and re-reads the result to verify the CRC.

`money` edits the raw JSON bytes in place, so the game's own number formatting is untouched.
`encrypt` writes whatever JSON you give it; keep the game's formatting (e.g. floats like
`9.969999694824219e+001`) if you edit by hand.

## Notes

- Story progress is in `timeline.m_timeline[name=main]` (`lexus2_c01` … `lexus2_c16`) plus
  `common_program_switch`; changing it by hand is unreliable (the game may restart the chapter).
- Tested on the Steam/2025 version under Proton.
