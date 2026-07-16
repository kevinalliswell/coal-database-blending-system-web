$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$SystemPython = "C:\Program Files\Python310\python.exe"
$Python = "python"
if (Test-Path $SystemPython) {
  $Python = $SystemPython
}
if (Test-Path $VenvPython) {
  try {
    & $VenvPython --version *> $null
    if ($LASTEXITCODE -eq 0) {
      $Python = $VenvPython
    }
  } catch {
    $Python = $SystemPython
  }
}

$Server = Join-Path $PSScriptRoot "https_server.py"
$LogDir = Join-Path $ProjectDir "logs"
$LogFile = Join-Path $LogDir "cbos-web.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ProjectDir

if (-not $env:FLASK_CONFIG) { $env:FLASK_CONFIG = "production" }
if (-not $env:DATA_STORAGE_MODE) { $env:DATA_STORAGE_MODE = "sqlite" }
if (-not $env:HOST) { $env:HOST = "0.0.0.0" }
if (-not $env:PORT) { $env:PORT = "8782" }
if (-not $env:SERVER_NAME) { $env:SERVER_NAME = "8.161.230.61" }
if (-not $env:REQUEST_TIMEOUT) { $env:REQUEST_TIMEOUT = "180" }

$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"

$CommandLine = '"' + $Python + '" "' + $Server + '" >> "' + $LogFile + '" 2>&1'
& cmd.exe /d /c $CommandLine
