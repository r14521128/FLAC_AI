# Itasca Three Brothers — Claude Skill Pack

Three production-ready Claude skills covering Itasca's flagship geomechanics codes:

| Skill | Product | Anchor path (Windows) |
|---|---|---|
| `flac3d-600` | FLAC3D 6.00 (continuum, FDM) | `C:\Program Files\Itasca\Flac3d600\` |
| `3dec-700` | 3DEC 7.00 (distinct element, blocks) | `C:\Program Files\Itasca\3DEC700\` |
| `pfc-itasca` | PFC 6.0 (DEM particles, bundled under FLAC3D 6 + 3DEC 7) | manual at `…\Flac3d600\pfchelp.chm`; examples at `…\3DEC700\DataFiles*D\PFC\` |

Each skill enforces strict no-fabrication rules — Claude refuses to invent commands or material parameters and cites the official install paths.

---

## 1. Prerequisites

You need at least one of the host products installed at the standard Itasca path:

- **FLAC3D 6.00** — needed for `flac3d-600` skill; also hosts the PFC manual (`pfchelp.chm`).
- **3DEC 7.00** — needed for `3dec-700` skill; also hosts the PFC example datafiles and provides the CLI host for running PFC (see §6).

Both default to `C:\Program Files\Itasca\Flac3d600\` and `C:\Program Files\Itasca\3DEC700\`. If yours are installed elsewhere (different drive, version suffix, …), see §4.

## 2. Install — Claude Code (CLI / desktop / IDE)

Drop the three folders into your Claude skills directory:

**Windows:**
```powershell
$dst = "$env:USERPROFILE\.claude\skills"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Expand-Archive -Path .\itasca_skills_pack.zip -DestinationPath $dst -Force
```

**Mac / Linux:**
```bash
unzip itasca_skills_pack.zip -d ~/.claude/skills/
```

Final layout:
```
~/.claude/skills/
├── flac3d-600/
├── 3dec-700/
└── pfc-itasca/
```

Restart Claude Code (or `/skill reload` in newer builds). The three skills should appear in `/skill list` and auto-activate on relevant queries (e.g. asking about `.f3dat`, `.dat` block models, or `ball generate`).

## 3. Install — Codex / other LLM agents

Codex doesn't natively support Claude's auto-activation, but the skills are pure markdown reference docs and work fine as attached context. Two patterns:

- **System prompt mode** — concatenate `<skill>/SKILL.md` + `<skill>/references/*.md` into the system prompt of your Codex session. Cheapest; works for one product at a time.
- **Retrieval mode** — index the files (e.g. with a vector store) and retrieve on demand. Best for multi-product environments. The pfc-itasca skill already includes `references/chm_extracted/` (3352 HTML files of the full PFC 6.0 manual) — point your indexer at this directory.

In either mode, the rules in §1 of each SKILL.md (the "Absolute engineering rules" — no invented commands, no fabricated parameters, cite-the-install) are the load-bearing content. Make sure they survive into your context.

## 4. Adapting to non-standard install paths

The skills hard-code Itasca's default Windows paths. If your install is elsewhere — different drive, EDU vs commercial suffix, newer minor version — do **either**:

- **Find/replace** the four canonical paths across all three skill folders:
  | Token | Your install |
  |---|---|
  | `C:\Program Files\Itasca\Flac3d600\` | your FLAC3D 6 root |
  | `C:\Program Files\Itasca\3DEC700\` | your 3DEC 7 root |
  | `C:/Program Files/Itasca/Flac3d600/` | (forward-slash form used in some examples) |
  | `C:/Program Files/Itasca/3DEC700/` | (forward-slash form) |

- **Or** symlink the standard paths to your real install (Windows admin shell):
  ```powershell
  New-Item -ItemType SymbolicLink -Path "C:\Program Files\Itasca\Flac3d600" -Target "D:\YourPath\Flac3d600"
  ```

The skills will refuse to invent answers if they can't reach the install, so wrong paths fail loud — which is the intended behavior.

## 5. PFC manual — extracted vs. fresh decompile

`pfc-itasca/references/chm_extracted/` ships with the PFC 6.0 manual already decompiled to HTML (3352 files, ~37 MB on disk) so Claude can `Grep`/`Read` it without setup. The source CHM lives at `C:\Program Files\Itasca\Flac3d600\pfchelp.chm`.

If your `pfchelp.chm` is a different revision (Itasca occasionally updates), re-extract:

```powershell
# hh.exe -decompile silently fails on paths with spaces — stage through C:\Temp
$tmpChm = "C:\Temp\pfchelp.chm"
$tmpOut = "C:\Temp\pfc_chm_out"
New-Item -ItemType Directory -Force -Path "C:\Temp", $tmpOut | Out-Null
Copy-Item "C:\Program Files\Itasca\Flac3d600\pfchelp.chm" $tmpChm -Force
Start-Process -FilePath "C:\Windows\hh.exe" -ArgumentList "-decompile", $tmpOut, $tmpChm -Wait
# Then replace pfc-itasca/references/chm_extracted/ with the contents of $tmpOut
```

This quirk is documented in the skill itself (`pfc-itasca/SKILL.md` §7c).

## 6. Running models from the CLI (verified)

Each skill has a `§9b` section in its `SKILL.md` with the production-tested invocation. Quick summary:

| Product | CLI |
|---|---|
| FLAC3D 6 | `flac3d600_console.exe <script>.f3dat` |
| 3DEC 7 | `3dec700_console.exe <script>.dat`  — **note: `.3ddat` is silently ignored**, rename or wrap |
| PFC | `3dec700_console.exe <script>.dat`  — script starts with `program load module 'pfc'`. **FLAC3D 6 console + PFC is broken (Qt/GUI issue) — use 3DEC host or the FLAC3D GUI.** |

Every script **must** end with `program quit` (or `quit`) for clean batch exit, and the launcher must close stdin (`< /dev/null` on bash, `$proc.StandardInput.Close()` on PowerShell). Without these the console hangs at the interactive prompt.

## 7. What's in each skill

```
flac3d-600/
├── SKILL.md                      ← rules, activation, CLI runner
└── references/
    ├── install_paths.md          ← canonical FLAC3D 6 install map
    ├── install_inventory.md      ← catalog of 850+ official .f3dat examples
    ├── v6_idioms.md              ← syntax patterns from real examples
    └── rules_digest.md           ← 1-page rules cheat sheet

3dec-700/
├── SKILL.md                      ← rules, activation, CLI runner + PFC host instructions
└── references/
    ├── doc_map.md                ← navigation map of 3DEC 7 HTML doc tree
    ├── constitutive_models.md    ← keyword tables for zone + joint models
    ├── rules_digest.md
    └── scripts_cheatsheet.md     ← one-page doc-navigation cheat sheet

pfc-itasca/
├── SKILL.md                      ← rules, activation, CLI runner via 3DEC host
└── references/
    ├── install_paths.md          ← path map (manual at FLAC3D, examples at 3DEC)
    ├── install_inventory.md      ← catalog of 2D + 3D PFC example folders
    ├── api_surface.md            ← entity taxonomy (balls, clumps, walls, contacts)
    ├── v_idioms.md               ← PFC syntax patterns from real .dat files
    ├── rules_digest.md
    └── chm_extracted/            ← full PFC 6.0 manual as 3352 HTML files (Grep-able)
```

## 8. License / versioning

The skills target specific product versions:
- FLAC3D 6.00 (build 069) — manual dated April 2017
- 3DEC 7.00 (build 7.00.126)
- PFC 6.0 (bundled manual dated April 17, 2019; public online mirror at `https://docs.itascacg.com/pfc600/` is the same major version, last updated Nov 19, 2021)

If you upgrade host products (FLAC3D 7+, 3DEC 8+), treat the corresponding skill as **read-only history** — the paths, file extensions, and command grammar all need re-verification against the new install. The skills are designed to fail loud rather than silently translate across versions.

## 9. Reporting issues / extending

These skills were built incrementally against the official install on a Windows 11 machine. If you find:
- A command the skill thinks doesn't exist but does → grep the install yourself and the skill's refusal rule will surface the gap; add to `references/v6_idioms.md` (or `v_idioms.md` for PFC) and re-bundle.
- A constitutive-model keyword mismatch → `references/install_inventory.md` points to the canonical example folders; verify and patch the keyword table in `SKILL.md §4`.
- An install on a different drive → see §4.

Have fun. Don't fabricate. — your brother
