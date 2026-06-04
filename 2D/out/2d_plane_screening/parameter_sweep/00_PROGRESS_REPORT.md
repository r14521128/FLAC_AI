# 目前進度彙報

日期：2026-05-27

## 已完成

1. 已將 Stage 1 改為 2D 無支撐解析解快速篩選。
2. 已移除噴凝土、支護壓力、shotcrete stiffness、shell、liner 與 equivalent support 對 Stage 1 計算與分數的影響。
3. 已將 `K0` 改為 `1.2`。
4. 已將候選參數改為每個 formation 的每個主要岩體參數由 min 到 max 取 100 個值，並用 deterministic LHS 做不同參數間的組合。
5. 已建立 hard filter、`score_2d`、`rank_2d`、`failure_flag`、`pass_stage1` 與 `reject_reason`。
6. 已輸出 Stage 2 可直接讀取的 passed CSV。
7. 已重新產生乾淨的 `01_2d_plane_screening.ipynb`。
8. 已新增 Stage 1 結果對比圖，輸出在 `figures/`。

## 本輪模型設定

- 隧道等效圓形半徑：`3.0 m`
- 隧道直徑：`6.0 m`
- 應力條件：`vertical_stress = density * g * overburden`
- 側壓係數：`K0 = 1.2`
- 位移估算：無支撐彈性收斂估算
- 塑性區估算：Kirsch 洞壁應力 + Mohr-Coulomb 破壞指標快速估算
- 噴凝土：未使用
- 監測資料：未使用

## 輸出規模

- 候選參數組：`100`
- 材料表列數：`500`
- Stage 1 內部檢核里程列數：`343100`
- all results CSV 列數：`500`
- passed for Stage 2 CSV 列數：`200`
- 通過 Stage 1 參數組：`40`
- 建議先進 Stage 2 參數組：`20`

## 主要輸出

正式輸出資料夾：

`out/2d_plane_screening/parameter_sweep/`

主要檔案：

- `stage1_2d_screening_all_results.csv`
- `stage1_2d_screening_passed_for_stage2.csv`
- `stage1_2d_screening_candidate_summary.csv`
- `stage1_2d_screening_material_table.csv`
- `stage1_2d_screening_summary.json`
- `stage1_2d_screening_summary.md`
- `figures/stage1_2d_score_ranking.png`
- `figures/stage1_2d_filter_summary.png`
- `figures/stage1_2d_displacement_vs_plastic_zone.png`
- `figures/stage1_2d_top20_stage2_candidates.png`
- `figures/stage1_2d_top20_E_heatmap.png`

## 目前限制與注意事項

- 2D 結果只作為快速篩選，不是最終監測校正結果。
- `plastic_zone` 欄位是 estimate，不是 FLAC3D 塑性區。
- `crown_settlement_mm` 為正值，代表向下/向內沉陷估算量。
- `wall_convergence_mm` 是左右側總收斂量。
- `tension` 與 `dilation` 在 Stage 1 保留空值，後續由 FLAC3D 小模型處理。
- Stage 2 應以 `parameter_set_id` 分組讀取 `stage1_2d_screening_passed_for_stage2.csv`。
