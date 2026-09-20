# Portable official CPython NuGet package; no installer, registry or system PATH edits.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if ([string]::IsNullOrWhiteSpace($env:CI_TASK_ROOT)) { throw 'CI_TASK_ROOT is required' }
if ([string]::IsNullOrWhiteSpace($env:CBOS_ARCHIVE_CACHE)) { throw 'CBOS_ARCHIVE_CACHE is required' }
function Get-VerifiedArchive($Name, $Url, $SHA256) {
    $archive = Join-Path $env:CBOS_ARCHIVE_CACHE $Name
    if (!(Test-Path -LiteralPath $archive)) {
        $download = Join-Path $env:CI_TASK_ROOT ($Name + '.download')
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 180 -Uri $Url -OutFile $download
        if ((Get-FileHash $download -Algorithm SHA256).Hash -ne $SHA256) { throw "Download checksum mismatch: $Name" }
        Move-Item -LiteralPath $download -Destination $archive
    }
    if ((Get-FileHash $archive -Algorithm SHA256).Hash -ne $SHA256) { throw "Cached package checksum mismatch: $Name" }
    return $archive
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$nodeZip = Get-VerifiedArchive 'node-v22.23.2-win-x64.zip' 'https://nodejs.org/dist/v22.23.2/node-v22.23.2-win-x64.zip' '1177b4137ba5adaa56354ae40f1080c7450e8ae09cecb47da459d1c52ac99f97'
[IO.Compression.ZipFile]::ExtractToDirectory($nodeZip, (Join-Path $env:CI_TASK_ROOT 'node'))
(Join-Path $env:CI_TASK_ROOT 'node/node-v22.23.2-win-x64') | Out-File $env:GITHUB_PATH -Append -Encoding utf8
$zip = Get-VerifiedArchive 'python.3.11.9.nupkg' 'https://api.nuget.org/v3-flatcontainer/python/3.11.9/python.3.11.9.nupkg' '9283876d58c017e0e846f95b490da3bca0fc0a6ee1134b2870677cfb7eec3c67'
$pythonRoot = Join-Path $env:CI_TASK_ROOT 'python'
[IO.Compression.ZipFile]::ExtractToDirectory($zip, $pythonRoot)
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
