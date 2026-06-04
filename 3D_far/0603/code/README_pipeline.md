# 0603 大模型管線 — 獨立執行說明

> 給任何「**跑在本機 Windows、有 PowerShell 終端權限**」的代理（Codex CLI / Claude Code / 人工）照著執行。
> ⚠️ FLAC3D 是本機授權軟體，**雲端沙箱無法執行**（碰不到安裝/授權/D槽檔案）。

---

## 1. 目的
石門水庫聯通管隧道「遠場大模型」的反算前處理：
1. **初始應力**（Mohr-Coulomb 材料含 tension + 重力 + K0=1.2 平衡）
2. **分段開挖 + 分段噴凝土 liner 支撐 + 監測**（隧道穿 SS_NC / 斷層 / SH_ST）

0603 相對 0601 的兩個修正：
- 各岩性**加 tension**（消除地表 tension=0 的數值潰散）
- 斷層段**加鋼纖維噴凝土 liner**（消除無支撐崩塌）

---

## 2. 環境
- FLAC3D 6.00 console：`C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe`
- 工作目錄：`D:\FLAC_AI\3D_far\0603`
- 幾何來源（restore）：`D:\FLAC_AI\3D_far\0601\step5_tunnel_marked.f3sav`（沿用 0601，不需複製）

---

## 3. 檔案清單
| 檔案 | 用途 | 狀態 |
|------|------|------|
| `initial_state.f3dat` | 初始應力 → 存 `initial_state_0603.f3sav` | ✅ 可跑 |
| `skel_excav_liner.f3dat` | 最小骨架（挖3段+上2段liner），驗證機制 | ✅ 測試用 |
| `excav_monitor.f3dat` | **完整分段開挖+liner+監測**（由骨架擴成）| ⏳ 建置中 |
| `run_pipeline.ps1` | 駁本：依序跑 initial_state → excavation，計時寫 `timing.log` | ✅ |
| `README_pipeline.md` | 本說明 | — |

---

## 4. 執行方式

### (A) 一鍵串接（推薦）
```powershell
powershell -ExecutionPolicy Bypass -File "D:\FLAC_AI\3D_far\0603\run_pipeline.ps1"
```
- 自動依序跑 `initial_state.f3dat` → `excav_monitor.f3dat`
- `initial_state_0603.f3sav` 若已存在 **會自動跳過**（可續跑）
- 每步開始/結束/花費時間寫入 `timing.log`

### (B) 個別執行
```powershell
$exe = "C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe"
& $exe "D:\FLAC_AI\3D_far\0603\initial_state.f3dat"
& $exe "D:\FLAC_AI\3D_far\0603\excav_monitor.f3dat"
```

---

## 5. 輸出
- `initial_state_0603.f3sav` — 初始應力存檔（~1 GB）
- excavation 的監測 CSV、checkpoint 存檔、final 存檔（檔名於 `excav_monitor.f3dat` 內定義）
- `timing.log` — 兩步驟花費時間
- 各 `.log` — FLAC3D 指令回顯（除錯用）

---

## 6. timing.log 範例
```
==== pipeline 開始 2026-06-03 ... ====
... START initial_state: ...initial_state.f3dat
... END   initial_state: elapsed = 01:10:00
... START excavation: ...excav_monitor.f3dat
... END   excavation: elapsed = 0X:XX:XX
==== pipeline 完成 ... ====
```

---

## 7. 材料 / 支撐參數
**Mohr-Coulomb（density young poisson cohesion friction tension）**，tension = cohesion×0.1（placeholder，待岩石 σt）：
| 岩性 | young | poisson | cohesion | friction | tension |
|------|-------|---------|----------|----------|---------|
| SS_NK | 1.2e9 | 0.29 | 300e3 | 38 | 30e3 |
| Interbedded_ST | 0.6e9 | 0.32 | 75e3 | 35 | 7.5e3 |
| SH_ST | 0.8e9 | 0.38 | 100e3 | 32 | 10e3 |
| SS_NC | 1.0e9 | 0.25 | 200e3 | 42 | 20e3 |
| Fault | 0.3e9 | 0.30 | 30e3 | 20 | 3e3 |

tunnel 依 x 分段：2500-2600 SS_NC、2600-2850 Fault、2850-3000 SH_ST。

**鋼纖維噴凝土 liner**（255 kgf/cm² = 25 MPa）：
- `struct liner property isotropic=(23.5e9, 0.2) thickness=0.2 density=2400`
- `struct liner property coupling-stiffness-normal=1e10 coupling-stiffness-shear=1e10 coupling-cohesion-shear=1e20`（結合/剛性界面）
- 建法（分段、落後1步）：把開挖區歸同一 `excavation` 群組，
  `struct liner create by-face range group 'excavation' not group 'tunnel' position-x <前一段>`
  （`not group 'tunnel'` 排除端面，同群組內部面不會被建 → 只上周邊環）

---

## 8. FLAC3D console 重要規則（踩過的雷）
- **每支 .dat 結尾必須有 `program quit`**，否則 console 跑完停在互動模式不退出。
- **headless 跑 .py 會崩**（`_ipython_cache` bug）→ 一律用 .dat / FISH，不要用 `pythonfile` headless。
- **FISH `local` 是函式範圍**：同一 `fish define` 內變數名不能重複（含 `loop foreach local`）。
- **一行只能一個 `[global ...]` / `local ...`**（多個會 `Bad conversion / Extraneous equals`）。
- **FISH 內 `command...end_command` 區塊在此 build 不被接受** → liner 等指令直接寫成命令、不要包在 fish 裡。
- `string.token` 會把逗號當分隔符；`gp.disp.x/y/z`、`gp.vel.x/y/z`、`zone.stress.xx()` 皆可寫入。

---

## 9. 注意事項
- ⚠️ **同一檔案不要兩邊同時跑**（搶 CPU/檔案鎖）。
- initial_state 的 `model solve elastic` 是兩階段（先彈性、再啟用塑性再平衡），會跑較久（~1–2h）。
- 收斂判據用 **ratio-average**（不是 ratio-local，後者會被開挖面單側受力點卡在 1.0）。
- excavation 每開挖步**強制至少 cycle `MIN_CYCLES`（目前 2000）**確保鬆弛。

---

## 10. 背景（為何做 0603）
0601 無支撐 + tension=0 → 斷層帶(63%)與地表(37%)數值崩塌、邊界位移失真（頂拱 -164m）。
0603 用 **tension + 斷層 liner** 修正，目標：開挖達穩定平衡、監測位移回到合理量級，再用於參數校正/反算。
詳見 `D:\FLAC_AI\3D_far\0601\ISSUE_boundary_collapse.md`。
