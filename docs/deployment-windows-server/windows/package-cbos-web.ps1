param(
  [Parameter(Mandatory = $true)]
  [string]$SourceRepo,

  [string]$OutputPath = (Join-Path $env:TEMP "cbos-web-deploy.tar.gz")
)

$ErrorActionPreference = "Stop"

$SourceRepo = (Resolve-Path -LiteralPath $SourceRepo).Path
if (-not (Test-Path -LiteralPath (Join-Path $SourceRepo "wsgi.py"))) {
  throw "SourceRepo does not look like coal-database-blending-system-web: $SourceRepo"
}
if (-not (Test-Path -LiteralPath (Join-Path $SourceRepo "frontend\dist\index.html"))) {
  throw "frontend\dist is missing. Run npm build in the source repo before packaging."
}

$OutputDir = Split-Path -Parent $OutputPath
if ($OutputDir) {
  New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
}

$items = @(
  "app",
  "backend",
  "migrations",
  "data",
  "static",
  "frontend/dist",
  "requirements.txt",
  "run.py",
  "wsgi.py",
  "pyproject.toml"
)

Push-Location $SourceRepo
try {
  if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
  }
  tar -czf $OutputPath @items
} finally {
  Pop-Location
}

Get-Item -LiteralPath $OutputPath | Select-Object FullName,Length,LastWriteTime
