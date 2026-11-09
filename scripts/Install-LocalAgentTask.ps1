[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$StartScript = Join-Path $RepoRoot "scripts\Start-LocalAgent.ps1"
$Config = Join-Path $RepoRoot "config\agent.local.json"
if (-not (Test-Path $Config)) {
    Copy-Item (Join-Path $RepoRoot "config\agent.example.json") $Config
    Write-Host "Created $Config. Review project paths and run this installer again."
    exit 0
}
$PowerShell = (Get-Command powershell.exe -ErrorAction SilentlyContinue).Source
if (-not $PowerShell) { $PowerShell = (Get-Command pwsh.exe -ErrorAction Stop).Source }
$ArgumentLine = '-NoProfile -ExecutionPolicy Bypass -File "' + $StartScript + '"'
$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument $ArgumentLine
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 5) -ExecutionTimeLimit ([TimeSpan]::Zero)
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "AutonomousEngineeringAgent" -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Local-only engineering review agent; no production or system security changes." -Force | Out-Null
Write-Host "Scheduled task installed for the current user. It starts at logon and restarts after failure."
