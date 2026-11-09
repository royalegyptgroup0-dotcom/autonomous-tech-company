[CmdletBinding()]
param()
$ErrorActionPreference = "Continue"

Write-Host "Local Engineering Agent — read-only prerequisite check" -ForegroundColor Cyan
Write-Host "No software will be installed, no model will be downloaded, and no settings will be changed."
Write-Host ""

function Show-CommandVersion([string]$Name, [string[]]$Arguments) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        Write-Host "[MISSING] $Name" -ForegroundColor Yellow
        return
    }
    $output = & $command.Source @Arguments 2>&1 | Select-Object -First 1
    Write-Host "[FOUND]   $Name — $output" -ForegroundColor Green
}

Show-CommandVersion "git" @("--version")
if (Get-Command py -ErrorAction SilentlyContinue) {
    Show-CommandVersion "py" @("-3", "--version")
} else {
    Show-CommandVersion "python" @("--version")
}
Show-CommandVersion "ollama" @("--version")

try {
    $computer = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
    $ramGiB = [math]::Round($computer.TotalPhysicalMemory / 1GB, 1)
    Write-Host ""
    Write-Host ("Installed physical RAM: {0} GiB" -f $ramGiB)
    if ($ramGiB -lt 8) {
        Write-Host "CAUTION: less than 8 GiB RAM; do not assume the 4B model will run comfortably." -ForegroundColor Yellow
    } else {
        Write-Host "RAM check: informational only; actual model performance depends on available memory and hardware." -ForegroundColor Green
    }
} catch {
    Write-Host "[UNKNOWN] Could not read physical RAM: $($_.Exception.Message)" -ForegroundColor Yellow
}

try {
    $driveLetter = [System.IO.Path]::GetPathRoot($env:LOCALAPPDATA).TrimEnd("\", ":")
    $drive = Get-PSDrive -Name $driveLetter -ErrorAction Stop
    $freeGiB = [math]::Round($drive.Free / 1GB, 1)
    Write-Host ("Free space on {0}: {1} GiB" -f $driveLetter, $freeGiB)
    if ($freeGiB -lt 8) {
        Write-Host "CAUTION: less than 8 GiB free; check storage before downloading a model." -ForegroundColor Yellow
    }
} catch {
    Write-Host "[UNKNOWN] Could not read free disk space: $($_.Exception.Message)" -ForegroundColor Yellow
}

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "Installed local Ollama models:"
    & ollama list
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Ollama model listing failed; verify that the local Ollama service is available." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "This check is advisory. It does not guarantee model compatibility or run the engineering agent."
