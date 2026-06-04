$ErrorActionPreference = "Stop"

$exe = "C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe"
$workdir = "D:\FLAC_AI\3D_small\0531\2608"
$script = Join-Path $workdir "run_read_far_boundary_sub_2608_logged.f3dat"
$status = Join-Path $workdir "out\read_far_boundary_sub_2608_status.txt"

"START $(Get-Date -Format o)" | Set-Content -LiteralPath $status -Encoding UTF8
$p = Start-Process -FilePath $exe -ArgumentList "`"$script`"" -WorkingDirectory $workdir -WindowStyle Hidden -PassThru -Wait
"END $(Get-Date -Format o) exit=$($p.ExitCode)" | Add-Content -LiteralPath $status -Encoding UTF8
