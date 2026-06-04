# FLAC3D 6.00 — Canonical install paths

The official installation at `C:\Program Files\Itasca\Flac3d600\` is the authoritative source of truth for this skill. Prefer reading these files directly over relying on indexed/parsed copies — the install is what FLAC3D actually executes against.

## Source of truth

| Resource | Path | Notes |
|---|---|---|
| Full HTML help (authoritative) | `C:\Program Files\Itasca\Flac3d600\flac3dhelp.chm` | CHM file. Itasca states: in any variance with the PDF excerpts, **the Help (CHM) wins**. |
| Manual PDFs (printable excerpts) | `C:\Program Files\Itasca\Flac3d600\HelpExcerpts\` | 3 PDFs — see table below. |
| Official `.f3dat` / `.f3prj` examples | `C:\Program Files\Itasca\Flac3d600\datafiles\` | 850 `.f3dat`, 167 `.f3prj`, 67 legacy `.dat`. See [install_inventory.md](install_inventory.md). |
| PFC help (related product) | `C:\Program Files\Itasca\Flac3d600\pfchelp.chm` | Only relevant if user combines FLAC3D with PFC. |
| Executable | `C:\Program Files\Itasca\Flac3d600\exe64\` | FLAC3D 6.00 binaries. |
| Console executable | `C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe` | Headless FLAC3D 6.00 console runner for batch `.f3dat` execution. |
| Plugin sources | `C:\Program Files\Itasca\Flac3d600\pluginfiles\` | C++ user-defined constitutive-model templates. |
| Building blocks | `C:\Program Files\Itasca\Flac3d600\BuildingBlockSets\` | Pre-built block geometries. |

## Manual PDFs (`HelpExcerpts/`)

| File | Size | Coverage |
|---|---|---|
| `flac3dmodeling.pdf` | 8.6 MB | Modeling guide — geometry, materials, BCs, solving, FISH, structural elements, plotting. |
| `theory.pdf` | 14 MB | Theory & background — formulation, constitutive models (zone + structural), fluid/thermal/dynamic theory, FoS. |
| `examples.pdf` | 15 MB | Worked examples — verification problems and example applications. |

These PDFs print as ~3000 pages combined. For lookup, prefer the `Read` tool with a tight `pages` range (max 20 pages per request) over reading the whole PDF.

## When to read what

| Question type | Read this first |
|---|---|
| "What does command X do?" | `flac3dhelp.chm` (or `flac3dmodeling.pdf` command reference section) |
| "How is constitutive model X formulated?" | `theory.pdf` |
| "Give me a worked example of Y" | Scan `datafiles\<topic>\<problem>\` for a matching folder; then `examples.pdf` if needed |
| "Show me v6 idiomatic .f3dat syntax" | Any `master.f3dat` under `datafiles\UsersGuide\Tutorial\` |
| "FISH intrinsic / pattern" | `datafiles\FISH\Library\` and `datafiles\FISH\Tutorial\` |
| "Structural element command" | `datafiles\Structure\<Beam|Cable|Geogrid|Liner|Pile|Shell>\` |
| "Verification benchmark" | `datafiles\VerificationProblems\<problem>\` |

## File-extension legend (FLAC3D 6.00)

| Extension | Meaning |
|---|---|
| `.f3dat` | Data file — primary v6 command-script format. |
| `.f3prj` | Project file — bundles `.f3dat` files, model state, plot/result configuration. |
| `.f3fis` | Standalone FISH script — v6 idiomatic. |
| `.fis` | Legacy FISH script (still supported). |
| `.dat` | Legacy v3/v5 data file — still callable but not the v6 idiom. |
| `.f3sav` | Saved model state. `model save "name"` auto-appends — do **not** write the extension in commands. |
| `.f3grid` | Saved grid only. |
| `.f3log` | Console log. |
| `.tab` | Table data. |
| `.acc`, `.his` | Acceleration / history records. |
| `.stl`, `.dxf` | Imported geometry. |

A typical example folder pairs `<Name>.f3dat` with `<Name>.f3prj` plus a `master.f3dat` that chains things together with `call '<file>'`.
