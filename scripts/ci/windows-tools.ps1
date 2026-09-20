# Portable official CPython NuGet package; no installer, registry or system PATH edits.
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if ([string]::IsNullOrWhiteSpace($env:CI_TASK_ROOT)) { throw 'CI_TASK_ROOT is required' }
$zip = Join-Path $env:CI_TASK_ROOT 'python.zip'
Invoke-WebRequest -UseBasicParsing -Uri 'https://api.nuget.org/v3-flatcontainer/python/3.11.9/python.3.11.9.nupkg' -OutFile $zip
if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne '9283876d58c017e0e846f95b490da3bca0fc0a6ee1134b2870677cfb7eec3c67') {
    throw 'Official Python NuGet package checksum mismatch'
}
$pythonRoot = Join-Path $env:CI_TASK_ROOT 'python'
Expand-Archive -LiteralPath $zip -DestinationPath $pythonRoot
$python = Join-Path $pythonRoot 'tools/python.exe'
& $python -c "import sys, struct; assert sys.version_info[:3] == (3, 11, 9); assert struct.calcsize('P') == 8"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$venv = Join-Path $env:CI_TASK_ROOT 'venv'
& $python -m venv $venv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
(Join-Path $venv 'Scripts') | Out-File $env:GITHUB_PATH -Append -Encoding utf8
$directories = @{
    'PIP_CACHE_DIR' = 'cache/pip'
    'npm_config_cache' = 'cache/npm'
    'ELECTRON_CACHE' = 'cache/electron'
    'ELECTRON_BUILDER_CACHE' = 'cache/electron-builder'
    'PYINSTALLER_CONFIG_DIR' = 'cache/pyinstaller'
    'TEMP' = 'temp'
    'TMP' = 'temp'
}
foreach ($name in $directories.Keys) {
    $path = Join-Path $env:CI_TASK_ROOT $directories[$name]
    New-Item -ItemType Directory -Force $path | Out-Null
    "$name=$path" | Out-File $env:GITHUB_ENV -Append -Encoding utf8
}
New-Item -ItemType Directory -Force 'outputs/ci' | Out-Null
