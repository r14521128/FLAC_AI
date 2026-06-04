# 踩雷與解法（Codex / Claude 共享）

> 這是**跨 AI 共享**的踩雷知識庫。Codex 或 Claude 在執行中遇到新坑、找到解法，**請依文末模板追加一條**。
> 精華版同步收錄在 repo 根 `CLAUDE.md` / `AGENTS.md` 的「FLAC3D Console 必備踩雷」一節；這裡放完整說明與案例。
> 最後更新：2026-06-04。

---

## A. FLAC3D Console 啟動與執行

### A1. 用 console exe、.f3dat 直接當參數、結尾要 `program quit`
- 用 `C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe`，**不要** GUI exe。
- 啟動：`Start-Process "<console.exe>" -ArgumentList '"<path>\file.f3dat"'`，路徑**直接當參數**，**不要**用 `call`。
- .f3dat **結尾必須** `program quit`。**Why:** console 從 PowerShell 啟動是非互動的，少了 `program quit` 會停在 `flac3d>` 互動模式、無法收輸入而 hang。

### A2. 要產生可監看的 log → `log-file` 必須配 `log on`
- `program log-file '...'` 只是**設定檔名**，預設 log 是 **off**。
- 必須緊接 `program log on` 才會真的寫 .log。
- **常見誤判**：smoke test「exit 0 但沒有 log 檔」**不代表** console 沒執行 .f3dat —— 多半是少了 `program log on`，io.out 只去了 stdout。對照 `excavation_lined_sub_*.f3dat` 第 8–9 行就是正確寫法。

### A3. 重型腳本背景跑 + 輪詢，不要前景等 timeout
- reader / excavation 動輒十幾分鐘（例：sub_2608 reader 要對 166MB 模型每個 zone 做 37,500 點 IDW）。前景 `&` 執行會被工具 10 分鐘 timeout 砍掉，**這不代表模型錯**。
- 正解：`Start-Process ... -WindowStyle Hidden` 背景跑，然後**用查詢判斷狀態**：
  - tail log：`Get-Content '<log>' -Tail 20`
  - 看 save 是否更新：`Get-Item '<save>.f3sav' | Select LastWriteTime, Length`
  - 看進程：`Get-Process flac3d600_console -ErrorAction SilentlyContinue`
- **完成判準（兩個一起看）**：log 出現結尾哨兵字串（如 `=== ... complete ===`）+ save 檔 `LastWriteTime` 變新。不要用時間盲猜。

### A4. 單授權，先確認沒有舊 console 在跑
- 本機 FLAC3D 是**單機單授權**。開新 console 前先 `Get-Process flac3d600_console`；若還在跑，不要再開第二支，否則授權衝突。

### A5. console 不支援內嵌 Python
- `python-run`、`program python-file` 不是合法指令。
- headless `pythonfile '...'` 會 crash（`AttributeError: ... '_ipython_cache'`，是 wrapper bug，與腳本內容無關）。
- 要跑 .py 只能在互動 IPython console `exec(open(...).read())`；**生產流程一律用純 .f3dat**。

---

## B. .f3dat / FISH 語法雷

### B1. 中文（CJK）註解吃換行 → 命令靜默不執行（致命）
- 一行 `;` 註解若**以中文字結尾、且下一行是命令**，console（用系統 codepage 讀 UTF-8）會把行尾 LF 吃掉，使下一行命令被併進註解而**不執行**，後續 FISH 常報莫名錯（如 `Arguments provided but not used`）。
- **Why:** UTF-8 多位元組的尾位元組被當成 Big5/CP950 lead byte，和 0x0A 配成一個字，吃掉換行。
- **解法：生產 .f3dat 一律 ASCII 註解**，中文說明放 HANDOFF / 文件。驗證：PowerShell 讀檔 bytes，`>0x7F` 數量應為 0。（中文註解若以 ASCII 字元如 `)`、數字結尾則不會中招。）

### B2. 多個 `[global ...]` 不要同一行
- 一行多個 inline-FISH `[global x = v]` 會 hang（`*** Unused extra parameter`）。**一行一個。**

### B3. FISH `local` 是函式作用域
- 同一 `fish define` 內同名重複宣告（含兩個 `loop foreach local g`、或 `local g=...` 後又 `loop foreach local g`）會報 `*** Fish: Local variable or argument previously defined`。
- 每個迴圈／暫存變數取**唯一名**（z/z2、g/gc/gd）。

### B4. FISH file IO 同時只能開一個檔、無 append
- `file.write(arr,n)` 沒有檔案參數 → 只寫「當前唯一開啟的檔」。
- 要同時產兩個輸出檔：大的（每步寫）當常駐開啟檔，小的緩衝在 FISH 陣列、最後再 `file.open(寫)`→寫→`close`。
- 讀檔慣用法：`file.open(p,0,1)`（0=讀,1=ASCII）→ `file.read(arr,1)` → `string.token(arr(1),k)`（吃逗號，回傳數值可直接運算）→ `gp.find(int(...))` / `zone.find(...)`。

### B5. 參數注入慣例
- 把材料／組合參數傳進 .f3dat：用 `[global name = value]`（一行一個），再於 `zone property` 用 inline `[name]`。
- save 檔名可組合：`model save ['prefix_' + combo_id]`。
- per-run 選擇可用環境變數：`.py` 內 `os.environ.get("FLAC_COMBO_ID","")`。

### B6. `model restore` 會洗掉「在 restore 之前」設的 FISH globals（致命）
- 現象：wrapper 先 `[global CSV_PATH/FINAL_SAVE/MONITOR_X/USE_LINER=...]` 再 `call core`，core 內第一行 `model restore`，跑完發現 `model save [FINAL_SAVE]` 存到 `0.f3sav`、CSV 完全沒產生、`gp.near(MONITOR_X,...)` 抓到 x=0 最近點（錯斷面）、`USE_LINER` 變 0（liner 不生成）。
- 原因（Why）：`model restore` 會把存檔當時的 **FISH 符號表整個還原**，等於清掉目前所有 globals；存檔（reader 產的 initial_state）沒有這些變數 → restore 後它們變未定義（求值=0/null）。RESTORE_NAME 之所以正常，是因為它在 restore「之前」就被用掉了。
- 解法（How）：**restore 必須放在 wrapper、且在設定 run-specific globals「之前」**；run-globals 一律設在 restore 之後才會存活。core 不要再 restore。順序：`model new`→`[global RESTORE_NAME=..]`→`model restore [RESTORE_NAME]`→`[global CSV_PATH/FINAL_SAVE/MONITOR_X/SMOKE_CAP/USE_LINER=..]`→`call core`。
- 來源：2026-06-04 Claude，小模型開挖 `3D_small/0531/excavation_lined_core.f3dat` + 6 個 wrapper；2896 unsup 首跑因此整批無效重跑。

---

## 追加模板（複製下面這段，填好貼到對應章節下）

```
### [編號] 一句話標題
- 現象：
- 原因（Why）：
- 解法（How）：
- 來源：<誰/哪支腳本/日期>
```
