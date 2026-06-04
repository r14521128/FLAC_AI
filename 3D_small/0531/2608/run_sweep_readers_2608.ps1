# ============================================================
# run_sweep_readers_2608.ps1
# 依序 headless 執行 5 組材料 reader (C01~C05)，產生
#   sub_2608_initial_state_cNN.f3sav  (材料 + IDW應力 + 切割邊界)
#
# 用法 (PowerShell):
#   powershell -ExecutionPolicy Bypass -File run_sweep_readers_2608.ps1
#
# 前置：far_out 內需有 initial_stress_sub_2608.dat (應力，已就緒)
#       與 submodel_boundary_displacement_v4.csv (位移，缺則邊界仍固定但無遠場位移值)
# ============================================================

$exe = "C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe"
$dir = "D:\FLAC_AI\3D_small\0531\2608"
$combos = @("c01","c02","c03","c04","c05")

foreach ($c in $combos) {
    $script = Join-Path $dir "run_$($c)_sub_2608.f3dat"
    if (-not (Test-Path $script)) {
        Write-Host ("  SKIP {0}: {1} not found" -f $c, $script)
        continue
    }
    Write-Host ("=== reader {0} ===" -f $c)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Start-Process -FilePath $exe -ArgumentList "`"$script`"" -WorkingDirectory $dir -Wait
    $sw.Stop()
    $sav = Join-Path $dir ("sub_2608_initial_state_{0}.f3sav" -f $c)
    if (Test-Path $sav) {
        Write-Host ("  OK {0}  elapsed {1}" -f $c, $sw.Elapsed)
    } else {
        Write-Host ("  FAILED {0} (no save produced)" -f $c)
    }
}
Write-Host "=== all readers done ==="
