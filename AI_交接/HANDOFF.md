# AI 對話交接文件 — 隧道開挖反算（0603）

> **給新對話冷讀用（Codex / Claude 通用）。** 這份只說明現況，**不要主動執行模擬**，除非使用者指示。
> FLAC3D 是本機授權軟體（單機、單授權），計算只能在這台 Windows 的 console 跑，雲端跑不了。
> 最後更新：2026-06-04。

---

## 0. 一句話現況
0601 大模型「無支撐」開挖數值崩塌 → 改用 **0603：斷層噴凝土 liner 支撐 + 各岩性加 tension**。
`initial_state_0603` 已建好（1h22m）。開挖監測碼 `code/excav_monitor.f3dat` 已 **修正完成且 4 步 smoke 全過**，**待正式全跑**（把 SMOKE_CAP 設 0，已設好）。

本輪（2026-06-03 下午）完成:
1. **liner bug 修正**:zone 群組 by-face（裹整塊 8740 面/段）→ 官方壁面法（face 群組 internal，**320 面/段**）。
2. **噴凝土不上仰拱**:`position-z [Z_LINER_BOT=215] [Z_LINER_TOP=221]`，只貼 z≥215（頂拱+側壁），留底部 ~1m 仰拱弧。
3. **小模型邊界匯出整合進開挖碼**:每步 conv 把 14236 個 box 邊界 gp 位移寫 `far_out/submodel_boundary_displacement.csv`（精簡格式）;另 `code/export_initial_stress_sub.f3dat` 匯初始應力。
4. **全碼改 ASCII 註解**（修掉中文吃換行的致命 bug）。

### 初始狀態驗證（2026-06-03，diag_*.f3dat in code/test/）
- **box 區域（z192-242）完全乾淨**:sub_2608(SS_NC+Fault 37500 zone)、sub_2896(SH_ST+Fault 37500)拉力降伏=0。
- 加 tension 後 SS_NK 仍 94%、Interbedded 60% 拉力降伏，**但它們是地表薄層**(SS_NK z384-472、Interbedded z283-430)，離隧道/box(z192-242)40~250m，artifact 不影響。
- **模型實際 z 延伸到 ~472**（HANDOFF 原寫 z170-265 只是隧道區段；地表/覆土在上）。σzz_min −6.45MPa@z177 對應 ~295m 覆土，合理。
- **初始應力已匯出並驗證**:`far_out/initial_stress_sub_2608/2896.dat`（各 37500 zone，全壓、量值合理）。

### ✅ 遠場大模型開挖已完成（54 步，存檔總循環 143097）
**支撐方案成功**:無崩塌、撐過斷層核心會合、位移砍 6-8 成。

**耗時**:開始 2026-06-03 16:44:46 → 結束 2026-06-03 22:13:49 = **約 5h29m**（54 個開挖步）。

**step 54 最終監測位移（mm，沉降為負；由 code/test/diag_monitor_gp.f3dat 從 excav_monitor_final 讀出）**:
| 斷面 | crown 沉降(z) | 左牆 wallL_y | 右牆 wallR_y | 收斂 conv(=−Ly+Ry) |
|------|------|------|------|------|
| 2608 | −28.2 | +29.8（內收） | −23.1（內收） | −52.9 |
| 2896 | −56.2 | +77.7（內收） | −81.2（內收） | −158.9 |
- 2896 明顯比 2608 軟(crown 2×、conv 3×) → 2896 落在斷層影響帶。
- 2608 左右不對稱(左 29.8 vs 右 23.1，差 6.7mm);2896 大致對稱(77.7 vs 81.2)。
- ⚠️ **以上為「界面焊死」假設值**(coupling-cohesion-shear=1e20、剛度 1e10 → liner 實際退化成 bonded shell、偏剛)→ 收斂屬「上限支撐/偏小」端;真實噴凝土界面會滑/脫,收斂只會更大。**界面參數已列校準待議**(見第 6 節)。

> **現場對比暫停**:使用者尚未提供真實現場監測資料。`data/monitoring/monitoring_data.csv` **不是**確認的現場資料,先不做任何模型 vs 現場比值/校準推論。繪圖已關現場參考線(`SHOW_FIELD=False`)。
- 位移曲線圖（3 資料夾×2 斷面）+ 繪圖碼:`0603/out/cycle_displacement_plots/`（`plot_cycle_displacement_0603.py`,現場參考線已關 `SHOW_FIELD=False`）。
- 輸出:`out/excav_monitor.csv`、`excav_monitor_final.f3sav`、`far_out/submodel_boundary_displacement.csv`(40.6MB)。
- ⚠️ **現有 `excav_monitor.csv` 只有 conv、沒有左右牆歷時**;上表左右牆值是事後 diag 補的最終值。`excav_monitor.f3dat` 已加 wallL/wallR 欄(下次跑會有),但**舊 CSV 無法回填**,要完整左右牆歷時得重跑(~5.5h)。

---

## 1. 專案
石門水庫至新竹聯通管隧道遠場大模型反算。隧道沿 x 軸穿三段岩性：
- SS_NC (x 2500–2600)、**Fault 斷層 (2600–2850)**、SH_ST (2850–3000)
- 監測斷面：**x=2608、x=2896**（crown gp≈(_,4800,220)、wall_L≈(_,4797,217)、wall_R≈(_,4803,217)）
- 模型範圍 x2500–3000, y4700–4900, z170–265；隧道 R=3m、y_c=4800、springline z=217

材料 Mohr-Coulomb（density young poisson cohesion friction **tension**）：
| 岩性 | young | poisson | cohesion | friction | tension(=c×0.1) |
|------|-------|---------|----------|----------|------|
| SS_NK | 1.2e9 | 0.29 | 300e3 | 38 | 30e3 |
| Interbedded_ST | 0.6e9 | 0.32 | 75e3 | 35 | 7.5e3 |
| SH_ST | 0.8e9 | 0.38 | 100e3 | 32 | 10e3 |
| SS_NC | 1.0e9 | 0.25 | 200e3 | 42 | 20e3 |
| Fault | 0.3e9 | 0.30 | 30e3 | 20 | 3e3 |

K0=1.2、重力 9.81。**tension 是 placeholder（cohesion×0.1），待岩石試驗 σt 取代。**
噴凝土 liner：E=23.5GPa（255kgf/cm²≈25MPa，ACI 4700√fc）、ν0.2、ρ2400、厚 0.2m、coupling 法向/剪向剛度 1e10、coupling-cohesion-shear 1e20。

---

## 2. 資料夾結構（已於 2026-06-03 整理）
```
D:\FLAC_AI\
├── AI_交接\                            ← 跨 Codex/Claude 共享區（2026-06-04 從 3D_far\ 移到專案根）
│   ├── HANDOFF.md                      ← 這份（進度交接）
│   ├── GOTCHAS.md                      ← 踩雷與解法
│   ├── CHANGELOG.md                    ← CLAUDE/AGENTS 變更記錄
│   └── 記憶共享方法.md
D:\FLAC_AI\3D_far\
├── 0603\
│   ├── timing.log                      ← pipeline 計時
│   ├── code\                           ← 【正式執行碼】
│   │   ├── excav_monitor.f3dat         ← 主開挖監測碼（liner 已修正）
│   │   ├── initial_state.f3dat         ← 建初始狀態（材料+邊界+初始應力）
│   │   ├── run_pipeline.ps1            ← 串接 initial_state→excavation、計時
│   │   └── README_pipeline.md
│   │   └── test\                       ← 【測試/骨架/反面參考】
│   │       ├── excav_monitor_v1_buggy.f3dat  ← 舊「裹整塊」錯版，反面教材
│   │       ├── excav_smoke.f3dat
│   │       └── skel_excav_liner.f3dat
│   ├── initial_state_0603.f3sav (938MB)   ← 【FLAC restore 讀取點】
│   ├── step5_tunnel_marked.f3sav (276MB)  ← 幾何輸入（initial_state restore 它）
│   ├── excav_monitor_final.f3sav          ← 正式跑完才產生（根目錄）
│   └── out\                            ← log + csv 輸出
│       ├── excav_monitor.log
│       └── excav_monitor.csv
```
**規則**：`.f3dat` 腳本放 `code\`（測試放 `code\test\`）；FLAC 讀寫的 `.f3sav` 放 `0603\` 根目錄；log/csv 放 `out\`。腳本內全用絕對路徑，移動位置不影響。

---

## 3. ⭐ liner bug 的診斷與修正（本次重點）

### 錯在哪（舊 v1，已封存 code\test\excav_monitor_v1_buggy.f3dat）
```
zone group 'linenow' range group 'excavation' position-x [xa] [xb]   ; 116 個 zone
struct liner create by-face range group 'linenow' not group 'tunnel' not group 'excavation'
```
用 **zone 群組** 配 by-face → 116 個 zone 竟生 **8740 個 liner 面**（每 zone 75 面，物理不可能）。代表它把整塊 zone 的所有面（內部面+端蓋+外側）都鍍 liner，而且**每段累積**（→20 萬+），造成：① 30° 對齊警告洪水 ② CPU 燒 6 小時 ③ log 漲到 431MB ④ **位移結果物理錯誤**（等於把開挖塊裹了一層超剛假殼，ratio 收斂漂亮是被箍死的假象）。

### 正解（官方 AdvancingLinedTunnel 同款，已套入 code\excav_monitor.f3dat）
用 **face 群組 + internal** 只取「圍岩↔開挖」之間、限制在當前段的壁面：
```
; 一次性（restore 後）：建圍岩群組
zone group 'rock' slot 'support' range group 'tunnel' not

; make_liner(xa,xb)：
zone face group 'wallnow' slot 'liner' internal range group 'rock' group 'excavation' position-x [xa] [xb]
struct liner create by-face id [g_lid] range group 'wallnow' slot 'liner'
struct liner property isotropic=(23.5e9,0.2) thickness=0.2 density=2400 range id [g_lid]
struct liner property coupling-stiffness-normal=1e10 coupling-stiffness-shear=1e10 coupling-cohesion-shear=1e20 range id [g_lid]
zone face group 'lined' slot 'liner' internal range group 'rock' group 'excavation' position-x [xa] [xb]  ; 重選同條件清空 wallnow
```
- `internal range group A group B` = A 區與 B 區「之間」的內部面（官方 IdentifyingRegions/groups2.f3dat 證實）。
- 每段唯一 `id`，屬性只套該 id；最後一行重選把面改標 'lined' 以清空 'wallnow'，避免累積重貼。
- **預期 liner 數從 8740/段 → 數十~數百/段**。

### liner vs shell（為何用 liner）
`liner = shell + 一層 Mohr-Coulomb 介面耦合彈簧`（法向 σn=kn·Δun、剪向 τ≤c+σn·tanφ 可滑動/脫開）。隧道噴凝土支撐靠這層把圍岩擠壓傳給襯砌；shell **沒有任何 coupling-* 屬性**，只在節點剛接，無法表現圍岩-襯砌接觸。出處：本機 `datafiles/Structure/Liner/LinerZoneInterfaceTest`、`AdvancingLinedTunnel`（liner 有 coupling）vs `Structure/Shell/AdvancingTunnel`（shell 無 coupling）。

---

## 4. 開挖腳本邏輯（code\excav_monitor.f3dat）
- restore `initial_state_0603` → 歸零位移/速度 → 建 'rock' 群組 → `warning off`
- 位置式左右推進：xL 從 tunnel x 最小往右、xR 從最大往左，到 2780 會合。`is_fine`（距監測 ±36m）決定一次挖 2m(fine) 或 10m(coarse)
- 每步：`excavate`（歸 excavation+null）→ 上「前一步」liner（落後 1 步，壁面法）→ `solve_step`（強制 ≥MIN_CYCLES=2000、達 ratio-average 目標、上限 20000）→ 寫 CSV
- 監測步（開挖面首次越過 2608/2896）：詳細記錄 cycle [50,100,200,300,400,500,1000] 後再收斂，並算塑性厚度
- `SMOKE_CAP`：>0 時只跑前 N 步（驗證用）；正式跑設 0
- 輸出：`out/excav_monitor.csv`（**file.write 緩衝，跑完 file.close 才落地**→ 跑中看進度要看 `out/excav_monitor.log` 的 io.out step 行，不是 CSV）、`excav_monitor_final.f3sav`（根目錄）

---

## 5. ⚠️ FLAC3D console / FISH 踩過的雷（務必遵守）
- **🔴 .dat 內中文註解若「以中文字結尾且下一行是命令」→ 行尾換行被吃掉、命令被併進註解而不執行**（console 用系統 codepage 讀 UTF-8，多位元組吃掉 LF）。症狀:命令靜默不跑、後面 FISH 報莫名錯。**生產碼一律用 ASCII 註解**（中文說明放這份 HANDOFF）。可用 PowerShell 驗:讀 bytes 數 >0x7F 的數量應為 0。
- **每支 .dat 結尾要 `program quit`**，否則 console 不退出（卡 flac3d> 提示、且會鎖住輸出檔）。
- **FISH file IO 同時只能開一個檔、且無 append 模式**（`file.write` 沒有檔案參數）。要同時輸出兩個檔時:把「大的、每步寫」的當常駐開啟檔，「小的」緩衝在 FISH 陣列最後再 `file.open(寫)`→寫→`close`。讀檔:`file.open(p,0,1)`→`file.read(arr,1)`→`string.token(arr(1),k)`（吃逗號）。
- **liner by-face 用 face 群組**:`zone face group N slot S internal range group A group B position-x .. position-z ..` →`struct liner create by-face id [n] range group N slot S`。屬性用 `range id [n]` 限定當段。**不要用 zone 群組 by-face**（會裹整塊、面數爆量）。
- **headless console 跑 .py 會崩**（_ipython_cache bug）→ 一律用 .dat/FISH。
- **FISH `local` 是函式範圍**：同一 fish define 內變數名不可重複（含多個 `loop foreach local g`）。用唯一名。
- **一行只能一個 `[global ...]`**（多個→Bad conversion/Extraneous equals 並卡死）。但**內嵌 `[expr]` 可多個一行**（如 `position-x [xa] [xb]`）。
- **`command...endcommand` 可用，loop 內也可**；內部引 FISH 變數用 `@var` 或 `[expr]`。
- **FISH 無 `|`/`or` 複合條件**（用單一旗標如 both_done 取代）；if 內相等比較單 `=` 可用，不等用 `#`。
- **liner `by-face` 不吃 `position-x` 直接限制 zone**；正解是 **face 群組 `internal range group A group B`**（見第 3 節）。
- **range 否定**：官方寫法是 **後綴** `range group 'X' not`（如 `range group 'concrete' not`）。
- **`warning off`**（top-level）關掉 liner 30° 對齊警告洪水（隧道轉角必然、無害）。已在主碼開頭。
- **收斂用 ratio-average（`zone.mech.ratio`）不是 ratio-local**（後者被開挖面單側受力點卡在 1.0）。average 太鬆 → 每步強制 MIN_CYCLES。
- **FLAC3D MC `tension` 預設=0**（不自動算）→ 已給各岩性加 tension。
- `gp.disp.x/y/z`、`gp.pos.*`、`zone.state(z,1)`、`gp.extra(g,i)`、`file.open/write/close`、`gp.near(x,y,z)` 皆可用。
- 單機單授權：**同時只能一支 console 在算**；idle console 會鎖住它開過的檔，清理前要先關。

---

## 6. 待辦 / 下一步
1. **smoke 驗證**（SMOKE_CAP=4）：看 `out/excav_monitor.log` 的 `struct liner create` → `--- N elements ... created`，**N 應數十~數百，非 8740**；無 parse error；CSV 有列。通過後把 SMOKE_CAP 改回 0。
2. **正式全跑** `code\excav_monitor.f3dat`（或 `code\run_pipeline.ps1`）。跑中監看 log 的 `step N` 行。
3. **驗收**：log 末出現 `=== EXCAV_MONITOR DONE ===`；讀 CSV 看 crown2608/conv2608/crown2896/conv2896 是否回 **mm 級合理值**（對比 0601 無支撐 crown -129/-205mm、conv2896 -422mm 的崩塌）。
4. 若位移仍偏大 → 調 tension（真實 σt）、liner 參數、或 MIN_CYCLES。
   - **校準待議**:(a) 全域 young 縮放 k_E、(b) 斷層帶額外處理、(c) **liner 界面從「焊死」改真實值**（coupling-cohesion-shear/friction 用噴凝土-岩界面實際量級,目前 1e20 等於 bonded shell、收斂偏小）。
5. **小模型切割邊界管線**（`3D_small/0531/2608,2896/`）暫停中，等 0603 大模型邊界乾淨後才有用。
6. 5 組材料掃描（只動 SH_ST/SS_NC/Fault 的 young/poisson/cohesion/friction）在乾淨大模型後進行。
7. 之後對比 `data/monitoring/monitoring_data.csv`（mm 級現場監測）做反算。

---

## 7. 關鍵數據速查
- **0603 有支撐最終(step54，耗時 5h29m)**：crown_2608 −28.2mm、conv_2608 −52.9mm（牆 +29.8/−23.1）；crown_2896 −56.2mm、conv_2896 −158.9mm（牆 +77.7/−81.2）。界面焊死假設、收斂偏小端。
- 0601 無支撐最終：crown_2608 -128.8mm、crown_2896 -204.6mm、conv_2896 -421.7mm
- 0601 崩塌：>1m 位移 56591 點（斷層 63%+地表 37%）、19% 流動、box 邊界頂拱 uz=-164m
- initial_state_0603 耗時 1h22m；舊 buggy v1 跑 6h 才到 step 17（已停）
- 相關記憶檔（使用者 .claude memory）：`feedback_flac3d_console.md`、`project_submodel_boundary_pipeline.md`
- console 執行：`& "C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe" "<script.f3dat>"`（工作目錄設 0603 根）

---

## 8. 下一階段：小模型開挖監測（★ 新對話從這裡開始）

**目標**：用乾淨的 0603 遠場結果，驅動兩個小模型（sub_2608、sub_2896）做高解析開挖監測，最終對比現場 `monitoring_data.csv` 反算。

### 8.1 遠場已備好的輸入（在 `D:/FLAC_AI/3D_far/0603/far_out/`）
| 檔 | 內容 | 給 reader 用 |
|----|------|------|
| `initial_stress_sub_2608.dat` / `_2896.dat` | 各 37500 zone 初始應力 `zid x y z sxx..syz`（空白分隔）| **格式與 reader 完全相符**，只要改路徑 |
| `submodel_boundary_displacement.csv` | 邊界 gp 位移歷時，**精簡格式** `step,phase,cycle,gp_id,ux,uy,uz` | ⚠️ 與 reader 不符（見下） |
| `submodel_boundary_gridpoints.csv` | `box_id,monitor_x,boundary,target_coord,actual_coord,gp_id,x,y,z`（14236 gp）| join 用 |

### 8.2 小模型管線位置 `D:/FLAC_AI/3D_small/0531/`
- `2608/read_far_boundary_sub_2608.f3dat`、`2896/read_far_boundary_sub_2896.f3dat`（reader：讀應力 IDW + 邊界位移 IDW → 固定六面邊界 → 存 `sub_*_initial_state`）
- `2608/sub_2608_build.f3sav`、`2896/sub_2896_build.f3sav`（已建好的小模型幾何）
- `2608/run_c01..c05_sub_2608.f3dat`（5 組材料 combo）、`run_sweep_readers_2608.ps1`
- `2608/excavation_unsupported.py`（小模型開挖，**Python，headless 會崩 → 要轉成 .dat/FISH**，可參照 0603 `code/excav_monitor.f3dat` 改寫）

### 8.3 ⚠️ 接上 0603 前必做的兩件事
1. **改 reader 的輸入路徑**：`read_far_boundary_sub_2608.f3dat` 第 41-42 行的 `stress_file`、`disp_file` 從 `0601/far_out` → `0603/far_out`。
2. **位移格式對接（關鍵）**：reader 的 `ReadBoundaryDisp` 預期 0601 **肥格式**（box_id@col11、x/y/z@17-19、ux/uy/uz@20-22），但 0603 是**精簡格式**（gp_id,ux,uy,uz）。兩條路：
   - **(建議) 預處理 join**：寫個 Python，把 `submodel_boundary_displacement.csv`（取**最後一步 step=54** 的列）join `submodel_boundary_gridpoints.csv`（by gp_id 補 box_id,x,y,z），輸出成 reader 吃的肥格式 → reader 幾乎不用改。
   - 或改 reader 的 `string.token` 欄位索引 + 自己讀 gridpoints.csv 補座標。
   - **注意**：reader 只取「該 box 最終收斂狀態(max step_pair/cycle)」當固定邊界 → **只需要 step=54 那批列**（不需全歷時）。

### 8.4 小模型材料（reader 內已設，沿用大模型；注意小模型 reader 目前**未加 tension**）
SS_NK/Interbedded/SH_ST/SS_NC/Fault 的 young/poisson/cohesion/friction 見 reader 第 48-68 行。box 內只有 SS_NC+Fault(2608) 或 SH_ST+Fault(2896)。**若要和 0603 一致，記得補 tension。**

### 8.5 建議流程
1. 預處理 join → 產 reader 吃的 0603 邊界位移檔（或改 reader）。
2. 改 reader 路徑 → 跑 `read_far_boundary_sub_2608/2896.f3dat` → 得 `sub_*_initial_state`。
3. 把小模型開挖（`excavation_unsupported.py`）改寫成 .dat/FISH（參照大模型開挖碼，**ASCII 註解**），加支撐 liner（同壁面法）。
4. 跑小模型開挖 → 監測位移 → 對比 `monitoring_data.csv`（H1 頂拱沉、D1/D2 收斂）。
5. 反算：調 k_E / young（遠場已知 ~1.55× 偏軟）逼近現場。

---

## 9. 每日進度自動報告 + Email（2026-06-04 建置）

無人值守、本機自動跑，**不需開 VSCode**。Codex 端不用維護，知道有這東西即可。

- **腳本**：`scripts/daily_report.py`（Python 3，純 stdlib，不畫圖）。
- **排程**：Windows 工作排程 `FLAC_AI_DailyReport`，每天 **09:00** 用 `pythonw.exe` 觸發。
  - 改時間：`Set-ScheduledTask -TaskName FLAC_AI_DailyReport -Trigger (New-ScheduledTaskTrigger -Daily -At 6:30pm)`
  - 手動跑：`python D:\FLAC_AI\scripts\daily_report.py`
  - 移除：`Unregister-ScheduledTask -TaskName FLAC_AI_DailyReport -Confirm:$false`
- **掃描範圍**：`2D / 3D_far / 3D_small / AI_交接`（改 `SCAN_ROOTS`）。
- **時間窗**：距上次報告以來（狀態檔 `output/daily_report/.last_report`，不漏不重複）。刪掉它會回看 24h。
- **報告內容（敘述式）**：每個資料夾用規則式判讀「做了什麼」，**不列檔名/日期**，而是分類敘述（開挖/改腳本/出存檔/出資料/更新文件）並從監測 CSV 即時抽**實際數據**：步數、是否收斂、斷面頂拱沉降(mm)、水平收斂(mm)、塑性區 zone 數、襯砌面數。兩種監測格式都支援（遠場 `crownNNNN_z`、小模型 `crown_uz`+`crown_x`）。**不自繪圖**。輸出 `output/daily_report/report_*.html`（本機留存）。
- **Email**：SMTP 寄到 ew2011626@gmail.com，**HTML 排版**敘述內文 + 把時間窗內**有更新的圖片檔直接當附件**（`.png/.jpg/...`，上限 30 張/20MB）。設定在 `scripts/mail_config.json`。
- **成本**：純 Python、**完全不呼叫任何 AI/雲端 API → 每天執行 0 額度、不花錢**。（與 Anthropic「Daily routine runs / 排程遠端 agent」不同，後者每跑一次算用量。）
  - ⚠️ `mail_config.json` 內含 Gmail **App Password（明文）** → **嚴禁進 git／上雲**，若 `git init` 要加 `.gitignore`。
