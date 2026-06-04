# align_agents.ps1
# 把 CLAUDE.md 對齊複製到 AGENTS.md（Claude 端 → Codex 端）。
# 用法：在 D:\FLAC_AI\ 終端機執行  .\align_agents.ps1
#       或在檔案總管對它按右鍵 → 用 PowerShell 執行。
# 建議：每 2~3 天、或剛改完 CLAUDE.md 後跑一次。

$ErrorActionPreference = 'Stop'
$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$claude = Join-Path $root 'CLAUDE.md'
$agents = Join-Path $root 'AGENTS.md'

if (-not (Test-Path $claude)) {
    Write-Host "[X] 找不到 $claude" -ForegroundColor Red
    exit 1
}

if ((Test-Path $agents) -and (-not (Compare-Object (Get-Content $claude) (Get-Content $agents)))) {
    Write-Host "[=] AGENTS.md 已與 CLAUDE.md 一致，無需對齊。" -ForegroundColor Green
    exit 0
}

Copy-Item $claude $agents -Force
Write-Host "[OK] 已對齊：CLAUDE.md -> AGENTS.md  ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))" -ForegroundColor Cyan
