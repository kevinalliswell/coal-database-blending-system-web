param(
  [string]$ArchivePath = "C:\Users\Shi Jinpeng\cbos-web-deploy.tar.gz",
  [string]$ProjectDir = "C:\srv\cbos-web",
  [string]$ServerName = "8.161.230.61",
  [int]$Port = 8782,
  [string]$Python = "C:\Program Files\Python310\python.exe",
  [string]$PipIndexUrl = "https://pypi.tuna.tsinghua.edu.cn/simple"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Invoke-NativeChecked {
  param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
  )

  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $FilePath $($Arguments -join ' ')"
  }
}

function New-HexSecret {
  $bytes = New-Object byte[] 32
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($bytes)
  ([BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
}

$ProjectDir = [System.IO.Path]::GetFullPath($ProjectDir)
$DeployKitRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$WindowsKit = Join-Path $DeployKitRoot "windows"
$ProjectWindowsDir = Join-Path $ProjectDir "deploy\windows"

if (-not (Test-Path -LiteralPath $ArchivePath)) {
  throw "Archive not found: $ArchivePath"
}
if (-not (Test-Path -LiteralPath $Python)) {
  throw "Python not found: $Python"
}
if (-not (Test-Path -LiteralPath (Join-Path $WindowsKit "https_server.py"))) {
  throw "Deploy kit is incomplete: $WindowsKit"
}

$serverScript = Join-Path $ProjectWindowsDir "https_server.py"
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object { $_.CommandLine -like "*$serverScript*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Stop-ScheduledTask -TaskName "cbos-web" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

New-Item -ItemType Directory -Force -Path $ProjectDir | Out-Null
tar -xzf $ArchivePath -C $ProjectDir

New-Item -ItemType Directory -Force -Path $ProjectWindowsDir | Out-Null
Copy-Item -LiteralPath (Join-Path $WindowsKit "https_server.py") -Destination $ProjectWindowsDir -Force
Copy-Item -LiteralPath (Join-Path $WindowsKit "start-cbos.ps1") -Destination $ProjectWindowsDir -Force
Copy-Item -LiteralPath (Join-Path $WindowsKit "requirements.txt") -Destination $ProjectWindowsDir -Force

$envFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path -LiteralPath $envFile)) {
  $secret = New-HexSecret
  @"
FLASK_CONFIG=production
DATA_STORAGE_MODE=sqlite
SECRET_KEY=$secret
HOST=0.0.0.0
PORT=$Port
SERVER_NAME=$ServerName
"@ | Set-Content -LiteralPath $envFile -Encoding UTF8
}

Push-Location $ProjectDir
try {
  Get-Content requirements.txt |
    Where-Object { $_ -notmatch "^gunicorn==" } |
    Set-Content requirements-windows-base.txt -Encoding ASCII

  Invoke-NativeChecked $Python -m pip install --retries 10 --timeout 120 -i $PipIndexUrl -r requirements-windows-base.txt
  Invoke-NativeChecked $Python -m pip install --retries 10 --timeout 120 -i $PipIndexUrl -r deploy\windows\requirements.txt

  $env:FLASK_CONFIG = "production"
  $env:DATA_STORAGE_MODE = "sqlite"
  $env:OMP_NUM_THREADS = "1"
  $env:OPENBLAS_NUM_THREADS = "1"
  $env:MKL_NUM_THREADS = "1"
  Invoke-NativeChecked $Python -c "from wsgi import app; print('APP_IMPORT_OK', app.name)"
} finally {
  Pop-Location
}

if (-not (Get-NetFirewallRule -DisplayName "CBOS Web 8782 HTTPS" -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName "CBOS Web 8782 HTTPS" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port | Out-Null
}

$taskArgs = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $ProjectWindowsDir "start-cbos.ps1") + '"'
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $taskArgs
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
Register-ScheduledTask -TaskName "cbos-web" -Action $action -Trigger $trigger -Principal $principal -Description "Coal blending optimization web console" -Force | Out-Null

Start-ScheduledTask -TaskName "cbos-web"
Start-Sleep -Seconds 10

$healthUrl = "https://127.0.0.1:$Port/health"
Invoke-NativeChecked curl.exe -k $healthUrl
Write-Output "DEPLOY_OK $healthUrl"
