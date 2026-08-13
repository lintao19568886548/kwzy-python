# LOCAL_STAGING_EQUIVALENT runner (not REMOTE_STAGING).
# Starts API with production-like flags, waits for /health, runs smoke.
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path "$Root\apps\api")) {
  $Root = "D:\重构python\kwzy-python"
}
$Api = Join-Path $Root "apps\api"
$Py = Join-Path $Api ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "missing venv python at $Py" }

$env:APP_ENV = "local"
$env:DEBUG = "false"
$env:ALLOW_ANON_DEV = "false"
$env:JWT_SECRET = "local-staging-jwt-secret-not-for-production-32"
$env:LOCAL_ADMIN_PASSWORD = "admin123"
$env:DATABASE_URL = "sqlite+pysqlite:///$($Api.Replace('\','/'))/local_staging.db"
$env:LOCAL_STAGING_API = "http://127.0.0.1:8000"

# free port 8000 if leftover
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

$proc = Start-Process -FilePath $Py -ArgumentList @(
  "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"
) -WorkingDirectory $Api -PassThru -WindowStyle Hidden

try {
  $ok = $false
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    try {
      $h = Invoke-RestMethod -Uri "$($env:LOCAL_STAGING_API)/health" -Method Get -TimeoutSec 2
      if ($h.status -eq "up") { $ok = $true; break }
    } catch { }
  }
  if (-not $ok) { throw "health not ready within 60s" }
  Write-Output "HEALTH=OK version=$($h.version) env=$($h.env)"
  & (Join-Path $PSScriptRoot "smoke.ps1")
  Write-Output "KWZY_LOCAL_STAGING_EQUIVALENT=PASS"
  exit 0
}
finally {
  if ($proc -and -not $proc.HasExited) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
  }
}
