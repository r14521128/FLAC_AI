$ErrorActionPreference = "Stop"

$base = "D:\FLAC_AI\3D_far\0530"
$console = "C:\Program Files\Itasca\Flac3d600\exe64\flac3d600_console.exe"
$stageTimeoutMs = 60000

$env:FLAC_SMOKE_MAX_STEP_PAIR = "1"
$env:FLAC_SMOKE_SOLVE_CAP = "500"

$stages = @(
    @{
        Name = "01_initial_state"
        Script = Join-Path $base "run_initial_state_0530_nopy.f3dat"
        RequiredOutputs = @(
            Join-Path $base "initial_state_0530.f3sav"
            Join-Path $base "far_out\initial_ratio_local.tab"
        )
    }
    @{
        Name = "02_unsupported_smoke"
        Script = Join-Path $base "02_unsupported_submodel_boundary_monitor_smoke.f3dat"
        RequiredOutputs = @(
            Join-Path $base "out\no_shotcrete_cycle_displacement_v4.csv"
            Join-Path $base "far_out\submodel_boundary_displacement_v4.csv"
            Join-Path $base "far_out\submodel_boundary_gridpoints_v4.csv"
        )
    }
    @{
        Name = "03_export_initial_stress"
        Script = Join-Path $base "03_export_initial_stress_to_submodel_boxes.f3dat"
        RequiredOutputs = @(
            Join-Path $base "far_out\initial_stress_sub_2608.dat"
            Join-Path $base "far_out\initial_stress_sub_2896.dat"
        )
    }
)

foreach ($stage in $stages) {
    Write-Host "=== running $($stage.Name): $($stage.Script) ==="

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $console
    $psi.Arguments = '"' + $stage.Script + '"'
    $psi.WorkingDirectory = $base
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $p = [System.Diagnostics.Process]::Start($psi)
    $p.StandardInput.Close()

    if (-not $p.WaitForExit($stageTimeoutMs)) {
        $p.Kill()
        throw "FLAC3D console timed out after $stageTimeoutMs ms for $($stage.Script)"
    }

    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    if ($stdout) { Write-Host $stdout }
    if ($stderr) { Write-Host $stderr }

    if ($p.ExitCode -ne 0) {
        throw "FLAC3D console failed with exit code $($p.ExitCode) for $($stage.Script)"
    }

    foreach ($path in $stage.RequiredOutputs) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw "Required output missing after $($stage.Name): $path"
        }
    }
}

Write-Host "=== smoke test complete ==="
