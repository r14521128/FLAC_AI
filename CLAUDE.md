# 專案快速參考：隧道反算 AI Agent

## 專案定位
石門水庫至新竹聯通管隧道銜接段工程的岩體勁度參數自動反算系統。
外部 Python 3 Orchestrator 透過 JSON 檔案控制 FLAC3D 6.0，搭配 Bayesian Optimisation 搜索最佳 Young's modulus 縮放係數。

---

## 🔗 跨 AI 共享記憶區（Codex / Claude 共用）

共享區位置：`AI_交接\`（在專案根目錄 `D:\FLAC_AI\AI_交接\`）
- `GOTCHAS.md` — 踩雷與解法。**遇到問題先查這裡**；找到新解法請追加一條。
- `HANDOFF.md` — 進度交接，**需要時再讀**（非每次對話）。
- `CHANGELOG.md`、`記憶共享方法.md` — 變更記錄與本機制說明。

註：`CLAUDE.md`（Claude 讀）與 `AGENTS.md`（Codex 讀）內容**相近即可，不必即時同步**，每 2~3 天對齊一次。

---

## 環境規格

| 層級 | 規格 |
|------|------|
| 外部 Orchestrator | Python 3.13.5，VSCode 終端 |
| FLAC3D 內嵌 | Python **2.7.9**，NumPy 1.9.2rc1 |
| 數值軟體 | FLAC3D **6.0** |
| 工作目錄 | `D:\FLAC_AI\` |
| 套件 | numpy, scipy, scikit-learn, pandas, matplotlib, sqlite3 |

---

## 反算參數空間（2 維）

```python
PARAM_NAMES = ["k_E", "k_E_fault"]
PARAM_BOUNDS = {
    "k_E":       (0.3, 3.0),   # Young 整體縮放係數
    "k_E_fault": (0.1, 1.0),   # 斷層帶額外縮放
}
```

### Young's modulus 計算
```python
Young_SS_NK  = k_E * 2.0e9   # Pa
Young_INT_ST = k_E * 1.0e9
Young_SH_ST  = k_E * 1.5e9
Young_SS_NC  = k_E * 2.5e9
Young_Fault  = k_E * k_E_fault * 0.5e9
```

### 固定參數（lab test medians）
各岩性群組的 cohesion / friction / tension / dilation / density / Poisson 皆為固定值，定義於 `flac3d/run_simulation.py` 的 `FIXED_PROPS`。

5 種岩性群組：`SS_NK` / `Interbedded_ST` / `SH_ST` / `SS_NC` / `Fault`

---

## 目錄結構

```
D:\FLAC_AI\
├── main.py                    # 入口：python main.py [--dry-run]
├── agents/
│   ├── orchestrator.py        # Phase 0~6 主迴圈
│   ├── simulation_agent.py    # 啟動 FLAC3D，管理 CSV
│   ├── calibration_agent.py   # GP Surrogate + Expected Improvement
│   └── lm_reporter.py        # LM Studio 自動報告
├── core/
│   ├── database.py            # SQLite CRUD (k_E, k_E_fault)
│   ├── loss_function.py       # RMSE + Pearson r
│   └── sampling.py            # Latin Hypercube Sampling (2D)
├── flac3d/
│   ├── material_setup.f3dat   # 【使用者提供】
│   ├── excavation.f3dat       # 【使用者提供】
│   ├── run_simulation.py      # Python 2.7，注入 params.json
│   └── params.json            # 【自動產生】當次迭代參數
├── data/
│   ├── calibration.db         # SQLite
│   ├── monitoring/monitoring_data.csv
│   └── results/run_XXXX.csv
└── output/calibration_report/
    ├── best_params.json
    ├── glue_analysis.csv
    └── convergence_plot.png
```

---

## 關鍵資料格式

### `flac3d/params.json`（Python 3 寫，Python 2.7 讀）
```json
{ "k_E": 1.2, "k_E_fault": 0.5 }
```

### `data/monitoring/monitoring_data.csv`
```
station,step_pair,H1_mm,D1_mm,D2_mm
2590,1,-1.2,-0.3,0.3
```
站點 x 座標：`2590 2608 2616 2878 2896 2926 2948`

### `data/results/run_XXXX.csv`（FLAC3D 輸出，單位：**公尺**）
```
step_pair,crown_2590_z,wall_L_2590_y,wall_R_2590_y,...
1,-0.00120,-0.00031,0.00029,...
```
loss_function.py 自動將 m 轉換為 mm 後比較。

---

## Loss Function

```
loss_i = 0.5 × RMSE_norm + 0.5 × (1 - Pearson_r)
total_loss = mean(loss_i)  對全部有效通道
```
RMSE 以觀測值範圍 `ptp(obs)` 正規化。

---

## FLAC3D 腳本整合要點

### `material_setup.f3dat` 必須呼叫參數注入腳本
```fish
python_run "flac3d/run_simulation.py"
```

### `excavation.f3dat` 結束時必須寫入 sentinel
```fish
def write_done_flag
  fp = open('flac3d/simulation_done.flag', 1, 0)
  oo = write_string("done", fp)
  oo = close
end
[ write_done_flag ]
```

### `flac3d/run_simulation.py`（Python 2.7 語法）
```python
import json, itasca as it
params = json.load(open("flac3d/params.json"))
k_E = params["k_E"]
k_E_fault = params["k_E_fault"]
# 計算 bulk/shear modulus → 賦值給各群組
```

---

## AI Agent 流程

```
Phase 0  初始化 DB + 載入監測資料
Phase 1  LHS 取樣（預設 10 組，2D 空間足夠）
Phase 2  寫 params.json → 啟動 FLAC3D → 等待 sentinel
Phase 3  讀 CSV → 計算 loss → 寫入 DB
Phase 4  重訓練 GP（scikit-learn GaussianProcessRegressor, 2D）
Phase 5  EI 最大化 → 取下一組候選參數
         收斂或達上限 → Phase 6
Phase 6  GLUE 分析輸出（loss < 1.5 × best_loss）
```

---

## 常用指令

```bash
python main.py --dry-run               # 測試全流程（無須 FLAC3D）
python main.py --dry-run --max-iter 8  # 快速測試
python main.py                         # 正式反算
```

### 啟動 FLAC3D console（**務必開可見視窗，讓使用者看進度**）
```powershell
$exe = "C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe"
$f3  = "<script.f3dat 絕對路徑>"
Start-Process -FilePath $exe -ArgumentList "`"$f3`"" `
  -WorkingDirectory "<工作目錄>" -WindowStyle Normal -PassThru
```
- **一律 `-WindowStyle Normal`，禁止 `-WindowStyle Hidden`**：使用者要能即時看到 console 進度。
- 完成判準用 **save 檔時間戳變新**，不要只 grep log 的 `complete ===`（log 是 append 模式，會殘留上一次成功的字串造成誤判）。
- **啟動前先檢查有沒有其他正在跑的 `flac3d600_console.exe`，有的話先回報它在幹嘛（跑哪支 .f3dat、啟動時間、佔多少記憶體），不要直接砍掉**——可能是別的計算正在正常跑。確認確實是殘留／要中止，再用 `Stop-Process -Id <PID> -Force` 指名砍：
  ```powershell
  Get-CimInstance Win32_Process -Filter "Name='flac3d600_console.exe'" |
    Select-Object ProcessId, CreationDate,
      @{n='Mem(MB)';e={[math]::Round($_.WorkingSetSize/1MB)}}, CommandLine
  ```

---

## 注意事項

- `flac3d/run_simulation.py` 只能在 FLAC3D 內部執行（需 `import itasca`）
- 外部 Python 3 的程式碼不可使用 `print "..."` 語法
- FLAC3D 6.0 輸出位移單位為**公尺**，監測資料單位為**毫米**
- 每次正式執行前請確認 `simulation_done.flag` 不存在（或程式會自動清除）
- FLAC3D / FISH 踩雷與解法 → 一律查 `AI_交接\GOTCHAS.md`
