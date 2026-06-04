# FLAC3D 6.00 — Rules Digest (1-page)

Condensed cheat sheet of the absolute rules in `SKILL.md`. Skim this before answering any FLAC3D question.

## Source of truth — the install

**Authoritative:** `C:\Program Files\Itasca\Flac3d600\`
- `flac3dhelp.chm` — full HTML Help (wins over PDFs in any variance)
- `HelpExcerpts\flac3dmodeling.pdf` · `theory.pdf` · `examples.pdf`
- `datafiles\` — 850 `.f3dat`, 167 `.f3prj`, 36 FISH scripts of official examples

**Workflow:** `Grep` `datafiles/` first for a live usage pattern → then PDF (with `pages:` range). The CHM is the most complete reference; decompile with `hh.exe -decompile` if needed.

## File extensions (v6)

| Ext | Meaning | Notes |
|---|---|---|
| `.f3dat` | v6 data file | primary script format |
| `.f3prj` | project file | bundles `.f3dat` + state |
| `.f3fis` | v6 FISH script | standalone FISH |
| `.fis` | legacy FISH | still supported |
| `.dat` | legacy data file | still callable; not idiomatic v6 |
| `.f3sav` | saved model | **auto-appended** in `model save`/`model restore` if missing; explicit `.f3sav` also accepted |
| `.f3grid` | saved grid | |
| `.tab`, `.acc`, `.his` | tabulated / accel / history data | |
| `.stl`, `.dxf` | imported geometry | |

## Hard rules

- **No invented commands.** Refuse if not retrievable from the install (`flac3dhelp.chm`, `HelpExcerpts/`, or `datafiles/`).
- **v6.00 syntax only.** No v3/v5 abbreviations, no v7-only constructs. When unsure, mirror `datafiles/UsersGuide/Tutorial/QuickStart/first.f3dat`.
- **No fabricated parameters.** `<TODO>` for E, ν, c, φ, ψ, K, ρ, k, ….
- **State assumptions:** dimensionality, units (m/kg/s/Pa), sign convention (compression negative), drainage, K0, gravity, water table, small/large strain, BCs.
- **Cite sources** with install paths: `datafiles/<Topic>/<Problem>/<file>.f3dat`, `HelpExcerpts/<pdf> §<section>`, or `flac3dhelp.chm → <topic>`.

## Mandatory `.f3dat` ingredients

1. `model new`
2. (often) `fish automatic-create off`
3. Geometry — `zone create … | zone import … | zone generate from-extruder`
4. `zone face skin` — auto-label boundary groups (East/West/North/South/Top/Bottom)
5. `zone cmodel assign <model>`
6. `zone property <keywords> <values>`
7. Boundary conditions — `zone face apply velocity-normal 0 range group '<X>'`, `model gravity 9.81`, etc.
8. Initial stress (recommended) — `zone initialize-stresses ratio <K0>`
9. `model history mechanical ratio-local` (convergence monitor)
10. `model solve` (or `model step <N>`)
11. `model save '<name>'` (no `.f3sav` extension in the command)

## Excavation

- `zone group '<name>'` (or `zone face skin`) **before** any excavation step.
- Two flavors:
  - `zone cmodel assign null range group '<name>'` — instant null
  - `zone relax excavate range group '<name>'` — graceful stress-relaxation
- Re-`model solve` / `model step` afterwards.
- Reference: `datafiles/ExampleApplications/ExcavationAndSupportOfShallowTunnel/`.

## Slope

- `model gravity` mandatory.
- SSR: `model factor-of-safety` (FLAC3D 6.00 form).
- Reference: `datafiles/ExampleApplications/SlopeCurvature/`.

## Groundwater coupling

- `model configure fluid`
- `zone fluid cmodel '<model>'`, `zone fluid property …`
- Pore-pressure BC: `zone gridpoint fix pore-pressure …` or `zone face apply pore-pressure …`
- Reference: `datafiles/Fluid/1DConsolidation/` (4 coupled/uncoupled variants).

## Dynamic / Thermal / Creep / Structural

- Dynamic: `model configure dynamic` + damping + quiet/free-field BCs + time-history input. Ref: `datafiles/Dynamic/EarthquakeExcitation/`.
- Thermal: `model configure thermal` + `zone thermal cmodel/property` + thermal BCs. Ref: `datafiles/Thermal/HollowCylinderConduction/`.
- Creep: `model configure creep` + a creep `zone cmodel` (power, WIPP, Maxwell, Kelvin, Burgers, …). Ref: `datafiles/Creep/`.
- Structural: `structure beam|cable|geogrid|liner|pile|shell create…` + `…property …`. Ref: `datafiles/Structure/<Element>/`.

## v6 syntactic conventions

- `;` — comment
- `...` (three dots, end of line) — line continuation
- `[expr]` — inline FISH expression
- `@func` — call FISH function `func`
- `call '<file>'` — chain another data file (often `call '<file>' suppress`)
- `'<string>'` — single quotes preferred for group names / paths in v6 examples

## Sanity heuristics

- Gravity ≈ 9.81 m/s² in SI (Itasca examples sometimes use 10 for round numbers).
- Density 1500–3000 kg/m³ in SI (flag kN/m³ or g/cm³ values).
- Every excavation `range group X` must have a matching upstream `zone group X` or `zone face skin`.
- `model save "name.f3sav"` — explicit extension is accepted (official examples use both forms).
- `@func` requires upstream `fish define func`.

## Refusal scripts (verbatim)

- **Unknown command** — “I cannot find this command in the FLAC3D 6.00 installation. Please verify against `flac3dhelp.chm` or the manual PDFs in `HelpExcerpts\`. I will not guess.”
- **Parameter without source** — “I will not fabricate engineering parameters. Please supply them from a site investigation report, lab test, or cited literature.”
- **Version mismatch** — “This skill targets FLAC3D 6.00. The command you mentioned looks like FLAC3D 5/7 or 3DEC syntax. Please confirm which version you are running.”
- **Out of scope** — “That falls outside FLAC3D 6.00. I can only answer from the v6.00 install at `C:\Program Files\Itasca\Flac3d600\`.”
