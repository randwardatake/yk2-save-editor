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

# jump to the start of a chapter (reads story data from the game's data/db.par)
./yk2save.py chapter save04/data.sav 2 --game-dir "/path/to/Yakuza Kiwami 2/runtime/media"

# manual editing: decrypt to JSON, edit, write back (CRC is recomputed)
./yk2save.py decrypt save01/data.sav save01.json
./yk2save.py encrypt save01.json save01/data.sav
```

Every write first copies the original to `~/.local/share/yk2save/backups/`
(override with `YK2SAVE_BACKUP_DIR`) and re-reads the result to verify the CRC.

`money` edits the raw JSON bytes in place, so the game's own number formatting is untouched.
`encrypt` writes whatever JSON you give it; keep the game's formatting (e.g. floats like
`9.969999694824219e+001`) if you edit by hand.

## Chapter jump

Use a copy of a real in-game save (not the New Game autosave) and load it from the title screen.

Story state lives in three places:

| Field | Meaning |
|---|---|
| `timeline.m_timeline[name=main].sheet[name=lexus2_cNN]` | per-chapter clock (`START`, step names like `ADV01_0040`, `END`) |
| same list, `common_program_switch` | which chapter's game logic is active (`START01` … `START10`) |
| `scene.m_scene_config_id` + `m_is_boot_config_id_only` | where the save boots; with the flag set the game starts that story step from scratch |

`scene_config` ids are row indexes of `data/db.par:scene_config.bin` (ARMP table) and map 1:1 to
story steps, e.g. `2854 = lexus2_ADV01_0040`, `2870 = lexus2_C02_0010`, `5934 = lexus2_fiction01`
(New Game opening). Chapter clock lists come from `data/db.par:timeline.bin`.

`chapter N` sets chapters `1…N-1` to `END`, chapter `N` to `START`, the switch to `STARTnn`, and
boots the save into the first step of chapter `N`, the same layout as the game's own chapter-start
saves.

What was tried:

| Attempt | Result |
|---|---|
| Only set `lexus2_c01=END`, `lexus2_c02=START02` on the New Game autosave | game ignored it and replayed the opening |
| Same plus `common_program_switch=START02` on an in-world save, no boot config | loads in Kamurocho with an empty objective list (broken state, chapter 1 events still fire) |
| Boot into `lexus2_C01_0120` (last chapter 1 cutscene) | untested (the next row worked first) |
| **`chapter 2`: boot config `2870` (`lexus2_C02_0010`) + clocks above** | **works**: chapter title and arrival in Sotenbori |

Chapters 3–10 are resolved the same way but untested. Chapters 11–16 use a different naming in
`timeline.bin` and are not supported yet.

## Notes

- Tested on the Steam/2025 version under Proton.
