---
name: flac3d-600
description: Use whenever the user works on FLAC3D 6.00 — command syntax (`zone …`, `model …`, `fish …`, `structure …`), FISH scripting, constitutive models (Mohr-Coulomb, Hoek-Brown, ubiquitous-joint, strain-softening, modified Cam-Clay, …), modeling workflows (tunnel excavation, slope SSR, staged excavation, groundwater coupling, structural elements, dynamic, thermal, creep, interface), reviewing or generating `.f3dat`/`.f3prj`/`.f3fis` skeletons, or answering geomechanics questions grounded in the official FLAC3D 6.00 install at `C:\Program Files\Itasca\Flac3d600\`. Activates on `.f3dat`/`.f3prj`/`.f3fis`/`.fis`/`.dat`/`.f3sav` files, FISH `fish define … end` blocks, or natural-language FLAC3D queries. Enforces strict no-fabrication rules — never invents commands or material parameters; cites the install paths.
---

# FLAC3D 6.00 Engineering Skill

This skill is the Claude-Code-native entry point to **the FLAC3D 6.00 product installation** at:

```
C:\Program Files\Itasca\Flac3d600\
```

That install **is the authoritative source of truth**. In particular:

- `flac3dhelp.chm` — the full HTML Help (Itasca's authoritative reference; PDFs are excerpts).
- `HelpExcerpts\` — three printable PDFs (`flac3dmodeling.pdf`, `theory.pdf`, `examples.pdf`).
- `datafiles\` — 1213 files of official Itasca worked examples, organized by topic: ConstitutiveModels, Creep, Dynamic, ExampleApplications, FISH, Fluid, Interface, Structure, TheoryAndBackground, Thermal, UsersGuide, VerificationProblems.

See [references/install_paths.md](references/install_paths.md) for the canonical map and [references/install_inventory.md](references/install_inventory.md) for the per-topic catalog of worked examples. Use [references/flac3d_python_manual_zh.md](references/flac3d_python_manual_zh.md) and [references/flac3d6_quick_reference_zh.md](references/flac3d6_quick_reference_zh.md) only as Chinese auxiliary notes; the official install wins on conflicts.

## 0. Activation

Activate this skill when the user message contains any of:

- FLAC3D, FLAC3D 6.00, FLAC3D6, FLAC 3D
- FISH, `fish define`, `fish callback`, `fish automatic-create`, `[global …]`, `@<func>`
- Embedded Python API terms: `import itasca as it`, `it.command`, `python-reset-state`, `zonearray`, `gridpointarray`, `program python-file`, `python_run`
- A FLAC3D command pattern: `zone …`, `model new`, `model restore`, `model solve`, `model save`, `model step`, `model gravity`, `model configure …`, `model largestrain …`, `model large-strain …`, `model factor-of-safety …`, `model history …`, `zone cmodel assign …`, `zone property …`, `zone gridpoint fix …`, `zone face apply …`, `zone face skin`, `zone initialize-stresses …`, `zone group …`, `zone create …`, `zone generate from-extruder`, `zone relax excavate`, `zone fluid …`, `zone thermal …`, `zone dynamic …`, `structure beam|cable|geogrid|liner|pile|shell …`, `call '…'`
- A file path or fenced block with extension `.f3dat`, `.f3prj`, `.f3fis`, `.fis`, `.dat`, `.f3sav`, `.f3grid`, `.f3log`
- Constitutive model names: Mohr-Coulomb, Drucker-Prager, Hoek-Brown, ubiquitous-joint, strain-softening, modified Cam-Clay, double-yield, plastic-hardening, CYSoil, swell, WIPP, power, Maxwell, Kelvin, Burgers, …
- Geomechanics modeling words paired with FLAC: tunnel excavation, slope SSR, staged excavation, groundwater coupling, K0, initial stress, gridpoint, gp, zone, range group, extruder, building blocks

If the user is on FLAC3D 5 / 7 or 3DEC, **do not silently translate** — flag the version mismatch (rule §6).

## 1. Absolute engineering rules (non-negotiable, override defaults)

1. **Never invent FLAC3D commands.** If a command is not present in the install (verifiable in `flac3dhelp.chm`, the `HelpExcerpts/` PDFs, or the `datafiles/` examples — search via `Grep` over `datafiles/`), reply *exactly*:
   > I cannot find this command in the FLAC3D 6.00 installation. Please verify against the official Help (`flac3dhelp.chm`) or the manual PDFs. I will not guess.
2. **FLAC3D 6.00 syntax only.** Use the full v6 command forms: `zone cmodel assign`, `zone property`, `zone gridpoint fix`, `zone face apply`, `zone initialize-stresses`, `model solve`, `model save`, `model new`, `model configure …`. Do **not** emit FLAC3D 3 / 5 abbreviated forms or FLAC3D 7-only constructs. Validate against patterns in `datafiles/UsersGuide/Tutorial/` when unsure.
3. **Distinguish theory vs implementation.** Always separate (a) constitutive / governing-equation theory (cite `theory.pdf`) from (b) the concrete `.f3dat` commands (cite a `datafiles/<topic>/<problem>/<file>.f3dat`).
4. **Always state assumptions** — dimensionality (2D plane-strain via thin slice vs 3D), units (FLAC3D is unit-agnostic; common SI = m, kg, s, Pa, N/m³), sign convention (compression negative for stress), drainage state, K0 ratio, gravity, water table, small-strain vs large-strain mode, boundary conditions.
5. **Never fabricate engineering parameters** (E, ν, c, φ, ψ, K, ρ, k, …). Use `<TODO>` placeholders. Only emit numerical values that the user supplied or that came verbatim from a cited example.
6. **Version mismatch:** if the user mixes FLAC3D 5/7 / 3DEC commands with 6.00 syntax, point it out.
7. **For excavation problems:** zone groups (`zone group …`) **must** be defined before any excavation step. Excavation = `zone cmodel assign null range group <name>` (or `zone relax excavate range group <name>` for graceful stress-relaxation excavation) followed by `model solve` / `model step`.
8. **For constitutive models:** always enumerate the exact `zone property` keywords required by that model in v6.00 (see §4 below). When unsure, open the matching folder in `datafiles/ConstitutiveModels/` — every cmodel has a runnable element-test example.
9. **Refusal on parameters without source:**
   > I will not fabricate engineering parameters. Please supply them from a site investigation report, lab test, or cited literature.
10. **Cite sources.** Prefer install-path citations: `datafiles/<Topic>/<Problem>/<file>.f3dat`, `HelpExcerpts/flac3dmodeling.pdf §<section>`, `HelpExcerpts/theory.pdf §<section>`, `HelpExcerpts/examples.pdf §<section>`, or `flac3dhelp.chm → <topic>`.
11. **`.f3sav` extension auto-appends.** `model save "name"` and `model restore "name"` auto-add `.f3sav` when the extension is missing. Explicit `"name.f3sav"` also works (some Itasca examples write it explicitly) — neither form is wrong.
12. **Local Chinese notes are secondary.** The two Chinese reference notes in `references/` are convenience summaries. Do not use them to override the official install, and ignore any non-official licensing/crack/DLL replacement content from external notebooks or local course files.

## 2. Response formats (use the exact section names)

### 2a. Command lookup ("what does X do?", "how do I write X?")

1. **Purpose** — one sentence.
2. **Syntax** — fenced block, FLAC3D 6.00 grammar (`<required>`, `[optional]`).
3. **Parameters** — bullets: keyword, meaning, unit, default.
4. **Minimal example** — short fenced `.dat` block.
5. **Common mistakes** — 2–4 bullets.
6. **Citations** — manual section.

### 2b. Modeling guidance (tunnel, slope, excavation, groundwater, …)

1. **Engineering problem definition**
2. **Modeling assumptions** (geometry, dimensionality, material model, drainage, initial stress, BCs, units)
3. **Workflow** — numbered stages
4. **FLAC3D commands** — grouped by stage
5. **Example `.dat` skeleton** — fenced, with `<TODO>` placeholders (no fictional numbers)
6. **Verification checklist** — 5–10 items (pull from `checklists/` in the knowledge base)

### 2c. FISH

1. Purpose
2. Function with v6.00 syntax (`fish define … end`)
3. FISH intrinsics used (`zone.list`, `gp.pos`, `zone.stress.xx`, …)
4. How to call (`[name]`, `fish list @var`)
5. Scope (model-state vs solve-time `fish callback add`)

### 2d. Constitutive model

1. Theoretical basis (yield surface, flow rule, hardening)
2. Required `zone property` keywords (see §4)
3. Optional keywords
4. Typical use cases
5. Limitations (e.g., MC unsuitable for cyclic loading; elastic unsuitable for failure prediction)

## 3. Knowledge-base map (read on demand — do not preload)

The FLAC3D 6.00 install is the authoritative source.

```
C:\Program Files\Itasca\Flac3d600\
├── flac3dhelp.chm                     ← full HTML Help (Itasca-authoritative)
├── HelpExcerpts\
│   ├── flac3dmodeling.pdf  (8.6 MB)   ← Modeling guide
│   ├── theory.pdf          (14 MB)    ← Theory & background
│   └── examples.pdf        (15 MB)    ← Worked examples
├── datafiles\                         ← 850 .f3dat + 167 .f3prj + 36 FISH + ...
│   ├── ConstitutiveModels\   (20 problems, element tests for each cmodel)
│   ├── Creep\                (14 problems)
│   ├── Dynamic\              (19 problems, seismic / time-history)
│   ├── ExampleApplications\  (19 realistic engineering cases)
│   ├── FISH\                 (Library + 33-lesson Tutorial)
│   ├── Fluid\                (17 groundwater problems)
│   ├── Interface\            (5 contact / joint problems)
│   ├── Structure\            (Beam, Cable, Geogrid, Liner, Pile, Shell)
│   ├── TheoryAndBackground\  (ElasticBlock, FactorOfSafety)
│   ├── Thermal\              (12 thermal problems)
│   ├── UsersGuide\           (Tutorial/QuickStart is the v6 starting point)
│   └── VerificationProblems\ (13 closed-form benchmarks)
├── exe64\                              ← FLAC3D 6.00 binaries
│   └── flac3d600_console.exe           ← headless console runner for batch .f3dat execution
├── pluginfiles\                        ← C++ user cmodel templates
└── BuildingBlockSets\                  ← pre-built block geometries
```

**Reading strategy for the install** — Claude should read on demand:

| Question type | Read first |
|---|---|
| Command syntax / what does X do? | `Grep` over `datafiles/` for live usage; then `HelpExcerpts/flac3dmodeling.pdf` (use `pages:` range) or `flac3dhelp.chm` |
| Constitutive theory | `HelpExcerpts/theory.pdf` |
| Worked example by topic | `datafiles/<Topic>/<Problem>/<file>.f3dat` (catalog in [references/install_inventory.md](references/install_inventory.md)) |
| v6 idiomatic syntax | `datafiles/UsersGuide/Tutorial/QuickStart/first.f3dat` (minimal end-to-end model) |
| FISH learning | `datafiles/FISH/Tutorial/fishex1_*.dat`, `fishex2_*.dat` |
| Embedded Python / `itasca` / array interface | [references/flac3d_python_manual_zh.md](references/flac3d_python_manual_zh.md), then verify against official Help / examples |
| Chinese quick lookup for v6 syntax | [references/flac3d6_quick_reference_zh.md](references/flac3d6_quick_reference_zh.md), then verify against official Help / examples |
| Structural elements | `datafiles/Structure/<Beam\|Cable\|Geogrid\|Liner\|Pile\|Shell>/<Problem>/` |
| Verification | `datafiles/VerificationProblems/<Problem>/` (closed-form benchmark) |

PDFs are large — always use `Read` with `pages:"start-end"` (max 20 pages). Never read a whole PDF.

## 4. Constitutive model required parameters (v6.00, authoritative)

Source: `config/skill_rules.yaml`. When the user picks a model, list these keywords *exactly* as `zone property` keys.

| `cmodel`              | required keywords                                                                                                              | optional                |
|-----------------------|--------------------------------------------------------------------------------------------------------------------------------|-------------------------|
| `elastic`             | bulk, shear                                                                                                                    | young, poisson          |
| `mohr-coulomb`        | bulk, shear, cohesion, friction, dilation, tension                                                                             | young, poisson          |
| `drucker-prager`      | bulk, shear, cohesion, friction                                                                                                | tension, dilation       |
| `hoek-brown`          | bulk, shear, constant-mb, constant-s, constant-a, constant-sci                                                                 | tension, dilation       |
| `ubiquitous-joint`    | bulk, shear, cohesion, friction, dilation, tension, joint-cohesion, joint-friction, joint-dilation, joint-tension, dip, dip-direction | —                       |
| `strain-softening`    | bulk, shear, cohesion, friction, dilation, tension, table-cohesion, table-friction, table-dilation, table-tension              | —                       |
| `modified-cam-clay`   | bulk, poisson, ratio-normal-consolidation, ratio-swelling, ratio-critical-state, pre-consolidation-pressure, specific-volume-reference | —                       |

If a model is requested that is not in this table, `Grep` for `zone cmodel assign <name>` over `datafiles/` and read the matching example before answering. **Never guess parameter keywords.**

## 5. Required commands per problem type (model_checker rules)

When generating or reviewing a `.f3dat` (or legacy `.dat`), ensure these are present. The pattern is corroborated against live examples in `datafiles/`.

- **generic** — `model new`; geometry (`zone create … | zone import … | zone generate from-extruder`); `zone face skin` (auto-labels N/S/E/W/Top/Bottom groups); `zone cmodel assign …`; `zone property …`; boundary or `model gravity`; `model solve` or `model step`; `model save '<name>'`. Recommended: `model largestrain on|off` or `model configure …`, `zone initialize-stresses ratio <K0>`, `model history mechanical ratio` (convergence monitoring).
- **excavation** — generic + `zone group '<name>'` (before excavation; or rely on `zone face skin` for boundary groups) + either `zone cmodel assign null range group '<name>'` (instant null) **or** `zone relax excavate range group '<name>'` (graceful stress relaxation). Reference: `datafiles/ExampleApplications/ExcavationAndSupportOfShallowTunnel/`.
- **slope** — generic + `model gravity`. SSR analyses use `model factor-of-safety` (with optional `model factor-of-safety strength-reduction` modifiers). Reference: `datafiles/ExampleApplications/SlopeCurvature/`.
- **groundwater** — generic + `model configure fluid` + `zone fluid cmodel '<model>'` + `zone fluid property …` + pore-pressure BC (`zone gridpoint fix pore-pressure …` or `zone face apply pore-pressure …`). Reference: `datafiles/Fluid/1DConsolidation/` (ships four coupled/uncoupled/fast-flow variants).
- **dynamic** — generic + `model configure dynamic` + appropriate damping (`zone dynamic damping …`) + quiet/free-field BCs (`zone face apply quiet …`, `zone dynamic free-field on`) + history input (`table read …`, `zone face apply …-history …`). Reference: `datafiles/Dynamic/EarthquakeExcitation/`.
- **thermal** — generic + `model configure thermal` + `zone thermal cmodel '<model>'` + `zone thermal property …` + thermal BCs (`zone gridpoint fix temperature …`, `zone face apply temperature …`, `zone face apply flux …`). Reference: `datafiles/Thermal/HollowCylinderConduction/`.
- **creep** — generic + `model configure creep` + `zone cmodel assign '<creep-model>'` (power, WIPP, Maxwell, Kelvin, Burgers, …) + `zone property …` for that model. Reference: `datafiles/Creep/`.
- **structural** — generic + `structure <element> create …` (or `structure <element> import from-geometry …`) + `structure <element> property …`. References: `datafiles/Structure/<Element>/`.

## 6. Heuristic sanity checks (apply when reviewing `.f3dat` / `.dat`)

- `model gravity` magnitude should be ~9.81 in SI (some Itasca examples use 10 for round numbers — note it but don't reject). Flag suspicious values.
- `property density` typically 1500–3000 kg/m³ in SI. Flag values that look like kN/m³ (15–30) or g/cm³ (1.5–3).
- `cmodel assign null range group '<X>'` — confirm group `X` was defined upstream via `zone group '<X>'` or auto-created by `zone face skin`. Otherwise nothing is excavated silently.
- `model save "name"` / `model restore "name"` — extension auto-appends (`.f3sav`) if missing. Explicit `"name.f3sav"` also accepted (rule §1.11).
- `call '<file>'` — confirm `<file>` exists relative to the current working directory. v6 idiomatic chaining uses `call '<file>.f3dat' suppress` (the `suppress` silences echo).
- `[…]` inline FISH — anything in square brackets is evaluated as a FISH expression. Flag obvious bracket-mismatch.
- `@<name>` — calls a previously-defined FISH function. Confirm `fish define <name>` exists upstream.
- `…` at end of a line — v6 line continuation. Don't confuse with an ellipsis comment.

## 7. Lookup workflow

Direct lookup against the install (always available, zero setup):

```
# command usage examples — grep over the 850 official .f3dat files
Grep pattern:"zone relax excavate" path:"C:/Program Files/Itasca/Flac3d600/datafiles" -C 2

# constitutive-model element test
Glob pattern:"datafiles/ConstitutiveModels/*MohrCoulomb*/*.f3dat"

# manual reference (read a narrow page range)
Read file_path:"C:/Program Files/Itasca/Flac3d600/HelpExcerpts/flac3dmodeling.pdf" pages:"120-135"
```

The PDFs are large; always use `pages:"start-end"` (max 20 pages per call). For the full HTML help (`flac3dhelp.chm`), open it in Windows Help Viewer or decompile with `hh.exe -decompile <out_dir> "<chm>"` for grep-able HTML.

## 8. Refusal scripts (use verbatim)

- Command not in install:
  > I cannot find this command in the FLAC3D 6.00 installation. Please verify against `flac3dhelp.chm` or the manual PDFs in `HelpExcerpts\`. I will not guess.
- Parameter without source:
  > I will not fabricate engineering parameters. Please supply them from a site investigation report, lab test, or cited literature.
- Wrong version:
  > This skill targets FLAC3D 6.00. The command you mentioned looks like FLAC3D 5/7 or 3DEC syntax. Please confirm which version you are running.
- Out of scope:
  > That falls outside FLAC3D 6.00. I can only answer from the v6.00 install at `C:\Program Files\Itasca\Flac3d600\`.

## 9. Quick-reference pointers (inside this skill)

- [references/install_paths.md](references/install_paths.md) — canonical install path map (what lives where).
- [references/install_inventory.md](references/install_inventory.md) — per-topic catalog of all 850 official `.f3dat` examples.
- [references/v6_idioms.md](references/v6_idioms.md) — v6 idiomatic syntax patterns distilled from official examples.
- [references/rules_digest.md](references/rules_digest.md) — condensed engineering rules for fast skim.
- [references/flac3d_python_manual_zh.md](references/flac3d_python_manual_zh.md) — Chinese auxiliary notes for FLAC3D 6.00 embedded Python 2.7.9, `itasca`, `zonearray`, `gridpointarray`, callback, and JSON/CSV integration.
- [references/flac3d6_quick_reference_zh.md](references/flac3d6_quick_reference_zh.md) — Chinese auxiliary quick reference for v6 command structure, `.f3dat`, FISH, tunnel workflow, and unit checks.

Read those when you need the rules without opening the full external knowledge base.

## 9b. Running a model via CLI (production-tested)

FLAC3D 6.00 ships a headless console binary that accepts a positional script argument and exits cleanly when the script reaches `program quit`.

**Executable:** `C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe`

### Minimal invocation

```powershell
& "C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe" "C:\path\to\model.f3dat"
```

Bash form (Git-Bash on Windows):
```bash
"C:/Program Files/Itasca/Flac3d600/exe64/flac3d600_console.exe" "C:/path/to/model.f3dat" < /dev/null
```

### Script requirements for clean exit

The console drops to an interactive `flac3d>` prompt at the end of a script. For batch use, **end the script with**:

```
program quit            ; synonyms: program stop, program exit, quit
```

Without it, the process hangs waiting for keyboard input — your harness will time out.

### Stdin handling

Always close stdin (`< /dev/null` in bash, `$p.StandardInput.Close()` in PowerShell `[System.Diagnostics.Process]::Start`). The console is interactive by default; if stdin is left open, it may still wait even after the script finishes.

### Logging

- `flac3d.log` is auto-created in the working directory on every run (no opt-in needed).
- The log echoes every executed command, useful for post-mortem.
- Override with `program log-file '<name>.log'` or disable with `program log off`.

### Project files via CLI

A `.f3prj` is a binary project bundle, not a script — it doesn't run directly. Open it in the GUI, or extract the `.f3dat` it references and run that.

### Watch-outs

- **Working directory** matters: `model save 'foo'` writes `foo.f3sav` to the current directory, not the script's directory. Set `cd` (Bash) / `WorkingDirectory` (PowerShell) deliberately.
- **Spaces in paths** are fine as long as you quote them (unlike `hh.exe -decompile`).
- **PFC commands under FLAC3D 6 console are NOT supported** — the PFC module DLLs are GUI-bound and the console hangs with a Qt connect warning. For PFC use the `pfc-itasca` skill's CLI recipe (3DEC 7 console host).
- **No `--help` flag** — the binary is interactive-first; flag-style help isn't implemented.

### Smoke test (verified to work)

```
model new
model title 'smoke test'
program quit
```

Running this via the invocation above on this machine produces `flac3d.log` with the command echo and exits with code 0. Verified 2026-05-25 against `flac3d Version 6.00 Release 069`.

## 10. Versioning

This skill targets **FLAC3D 6.00 only**. Sources of truth:

- Install root: `C:\Program Files\Itasca\Flac3d600\` (`totalversion.txt` records the exact build)
- Help: `flac3dhelp.chm` (authoritative) + `HelpExcerpts\` (printable PDFs, *Sixth Edition, April 2017*)
- Examples: `datafiles\` (Itasca-shipped, run-able under this install)

If the user upgrades to FLAC3D 7+, treat this skill as read-only history — point them at the v7 install and refuse to translate commands silently.
