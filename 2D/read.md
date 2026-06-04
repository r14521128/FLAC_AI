# D:\FLAC_AI\2D 資料夾整理說明

本專案根目錄只保留四個主要資料夾：

- `code`
- `int`
- `out`
- `monitor`

後續新增檔案請依照下列規則放置，避免根目錄再次混亂。

## code

用途：放程式碼、notebook、程式產生器與輔助函式參考。

目前主要內容：

- `01_2d_plane_screening.ipynb`：2D 解析/半解析快速篩選 notebook。
- `create_01_2d_plane_screening_notebook.py`：產生或重建 2D notebook 的 Python 腳本。
- `reference_profile_functions.txt`：剖面或函式參考資料。
- `__pycache__`：Python 執行後產生的快取。

注意：

- 從 `code` 內執行 notebook 時，程式已會自動往上一層尋找專案根目錄，所以仍會讀取 `D:\FLAC_AI\2D\int` 與輸出到 `D:\FLAC_AI\2D\out`。

## int

用途：放模型前處理輸入資料，不放程式輸出。

目前主要內容：

- `Shimen_Tunnel_3D_Alignment_1m.csv`：隧道中心線或剖面里程資料。
- `00_material_parameter_statistics.csv`：地層材料參數統計表。
- `.ply` 地質面與地形資料。
- `石門隧道輪數對應表.xlsx`：輪數與里程對應資料。

注意：

- 目前 `00_material_parameter_statistics.csv` 沒有正式 `q75` 欄位，因此 Q75 是由 `min/max` 線性估算。

## out

用途：放所有分析輸出、圖、CSV、JSON、報告與整理結果。

目前主要內容：

- `2d_plane_screening/parameter_sweep`：目前正式的 2D 參數組合篩選輸出資料夾。
- `2d_plane_screening/root_archive`：原本散在根目錄的舊輸出副本，已搬入此處歸檔。
- `2d_plane_screening/README.md`：2D 篩選輸出資料夾說明。
- `cache/.uv-cache`：工具執行過程產生的快取。
- `00_data_check.csv`、`00_int_data_check.csv`：資料檢查輸出。

正式資料請優先使用：

`out/2d_plane_screening/parameter_sweep`

## monitor

用途：放監測資料與監測圖表，不作為開挖前 2D 快速篩選主要輸入。

目前主要內容：

- `00_monitor_plot_summary.csv`
- 各監測點資料夾，例如 `T-19`、`T-20`、`T-36`
- 各監測點的 summary CSV 與 section displacement 圖

注意：

- 監測資料目前只保留為後期驗證與校正依據。

## 目前工作進度

已完成：

- 2D 快速篩選流程整理。
- 噴凝土等效支撐厚度組合：`0.00, 0.10, 0.20, 0.30 m`。
- 地層參數等級組合：`min, Q25, average, Q75, max`。
- 20 組 case summary。
- 6 組 FLAC3D 代表案例挑選。

尚未完成：

- 尚未執行 FLAC3D。
- 尚未使用監測資料進行後期校正。

## 檔案放置規則

- 程式碼與 notebook：放 `code`
- 原始輸入資料：放 `int`
- 分析輸出與報告：放 `out`
- 監測資料與監測圖：放 `monitor`
- 根目錄只放本說明檔 `read.md`
