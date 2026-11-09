[CmdletBinding()]
param([string]$ConfigPath = (Join-Path $PSScriptRoot "..\config\agent.local.json"))
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ConfigPath = [System.IO.Path]::GetFullPath($ConfigPath)
if (-not (Test-Path $ConfigPath)) {
    throw "Missing config: $ConfigPath. Copy config\agent.example.json to config\agent.local.json and configure project paths."
}
$Python = Get-Command py -ErrorAction SilentlyContinue
if ($Python) { & py -3 "$RepoRoot\local_agent\engine.py" --config "$ConfigPath" --loop }
else { & python "$RepoRoot\local_agent\engine.py" --config "$ConfigPath" --loop }
exit $LASTEXITCODE
