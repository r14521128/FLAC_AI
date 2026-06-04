# 2D plane screening 輸出資料夾說明

本資料夾作為 2D 解析/半解析快速篩選流程的輸出位置。

## 正式資料來源

正式資料請優先使用：

`out/2d_plane_screening/parameter_sweep/`

後續整理、彙報與 FLAC3D 案例挑選，應以 `parameter_sweep` 內的檔案為主。

## 子資料夾

- `parameter_sweep/`：目前已完成的地層參數等級與噴凝土厚度組合篩選結果。
- `root_archive/`：原本散在根目錄的舊輸出副本，已搬入此處歸檔，避免根目錄混亂。
- `cache/`：工具或執行過程產生的快取。

## 注意事項

- 目前尚未執行 FLAC3D。
- 目前監測資料未作為 2D 篩選輸入，只保留為後期驗證使用。
- `Q75` 目前由 `min/max` 線性估算，正式 Q75 統計資料補上後需重跑。
