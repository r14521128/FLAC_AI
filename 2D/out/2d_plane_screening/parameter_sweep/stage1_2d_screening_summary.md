# Stage 1 2D Screening Summary

## Run Summary
- Total candidate parameter sets: 100
- Hard-filter rejected: 100
- Passed Stage 1: 0
- Formation-level rejected rows: 185
- Formation-level passed rows: 115
- Recommended Stage 2 parameter sets: 0
- Support assumption: unsupported; no shotcrete; no equivalent support

## Formula Check
- Screening mode: `plastic_zone_only`
- Failure criterion: `generalized_hoek_brown`
- Hoek-Brown disturbance factor: `D = 0.5`
- Settlement and wall convergence are disabled in this screening run.
- Plastic-zone filters are applied per formation using segment P95, not a single whole-tunnel maximum.
- `score_2d` is controlled by the worst passed formation score and uses only plastic-zone ratio, Hoek-Brown stability index, and parameter prior penalty.

## Top Ranked Parameter Sets
| parameter_set_id | rank_2d | score_2d | p95_plastic_zone_m | plastic_ratio | max_stability_index | danger_formation |
|---|---:|---:|---:|---:|---:|---|
| P0049 | 1 | 2.0708 | 6.51 | 2.171 | 501.53 | Interbedded_ST |
| P0030 | 2 | 2.0739 | 6.52 | 2.174 | 507.04 | Interbedded_ST |
| P0038 | 3 | 2.0758 | 6.50 | 2.167 | 496.08 | Interbedded_ST |
| P0050 | 4 | 2.0774 | 6.57 | 2.190 | 529.76 | Interbedded_ST |
| P0041 | 5 | 2.0789 | 6.55 | 2.182 | 518.27 | Interbedded_ST |
| P0005 | 6 | 2.0836 | 6.56 | 2.186 | 523.98 | Interbedded_ST |
| P0059 | 7 | 2.0983 | 6.63 | 2.209 | 559.73 | Interbedded_ST |
| P0096 | 8 | 2.1047 | 6.64 | 2.213 | 565.95 | Interbedded_ST |
| P0031 | 9 | 2.1101 | 6.60 | 2.201 | 547.53 | Interbedded_ST |
| P0039 | 10 | 2.1114 | 6.62 | 2.205 | 553.60 | Interbedded_ST |

## Figures
- score_ranking_png: `D:\FLAC_AI\2D\out\2d_plane_screening\parameter_sweep\figures\stage1_2d_score_ranking.png`
- filter_summary_png: `D:\FLAC_AI\2D\out\2d_plane_screening\parameter_sweep\figures\stage1_2d_filter_summary.png`
- plastic_zone_score_png: `D:\FLAC_AI\2D\out\2d_plane_screening\parameter_sweep\figures\stage1_2d_plastic_zone_score.png`
