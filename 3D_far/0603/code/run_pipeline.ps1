# ============================================================
# run_pipeline.ps1
# 串接駁本：依序跑 initial_state -> excavation，各自計時，寫入 timing.log
# 用法: powershell -ExecutionPolicy Bypass -File run_pipeline.ps1
#
# - initial_state：若 initial_state_0603.f3sav 已存在則跳過（可續跑）
# - 每一步記錄 開始/結束/花費時間 到 timing.log
# ============================================================
$exe = "C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe"
$dir = "D:\FLAC_AI\3D_far\0603"       # f3sav 讀寫的根目錄
$codedir = Join-Path $dir "code"      # .f3dat 腳本所在
$timing = Join-Path $dir "timing.log"

function Run-Stage($name, $script, $expectSave) {
    if ($expectSave -and (Test-Path $expectSave)) {
        ("{0}  SKIP {1} (save 已存在)" -f (Get-Date), $name) | Tee-Object -FilePath $timing -Append
        return
    }
    $start = Get-Date
    ("{0}  START {1}: {2}" -f $start, $name, $script) | Tee-Object -FilePath $timing -Append
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Start-Process -FilePath $exe -ArgumentList "`"$script`"" -WorkingDirectory $dir -Wait
    $sw.Stop()
    $end = Get-Date
    ("{0}  END   {1}: elapsed = {2}" -f $end, $name, $sw.Elapsed.ToString()) | Tee-Object -FilePath $timing -Append
}

("==== pipeline 開始 {0} ====" -f (Get-Date)) | Tee-Object -FilePath $timing -Append
Run-Stage "initial_state" (Join-Path $codedir "initial_state.f3dat")   (Join-Path $dir "initial_state_0603.f3sav")
Run-Stage "excavation"    (Join-Path $codedir "excav_monitor.f3dat")   (Join-Path $dir "excav_monitor_final.f3sav")
("==== pipeline 完成 {0} ====" -f (Get-Date)) | Tee-Object -FilePath $timing -Append
