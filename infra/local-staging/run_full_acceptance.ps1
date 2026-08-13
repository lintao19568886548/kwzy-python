# Full local staging acceptance with real exit codes and timings.
$ErrorActionPreference = "Stop"
$Root = "D:\重构python\kwzy-python"
$Api = Join-Path $Root "apps\api"
$Web = Join-Path $Root "apps\web"
$Py = Join-Path $Api ".venv\Scripts\python.exe"
$ReportDir = Join-Path $Root "infra\local-staging\out"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$report = @()
function Step($name, $scriptBlock) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $code = 0
  $out = ""
  try {
    $out = & $scriptBlock 2>&1 | Out-String
  } catch {
    $code = 1
    $out = "$_"
  }
  $sw.Stop()
  if ($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0) { $code = $LASTEXITCODE }
  $entry = [ordered]@{
    step = $name
    exit_code = $code
    ms = $sw.ElapsedMilliseconds
    output_tail = ($out.Trim() -split "`n" | Select-Object -Last 8) -join "`n"
  }
  $script:report += $entry
  Write-Output ("STEP={0} EXIT={1} MS={2}" -f $name, $code, $sw.ElapsedMilliseconds)
  if ($code -ne 0) { throw "step failed: $name" }
  return $out
}

$env:POSTGRES_PASSWORD = "kwzy_test_local_only"
$env:TEST_DATABASE_URL = "postgresql+psycopg://kwzy_party_test:kwzy_test_local_only@127.0.0.1:55432/kwzy_party_test"
$env:POSTGRES_TEST_URL = $env:TEST_DATABASE_URL
$env:ETL_DATABASE_URL = $env:TEST_DATABASE_URL
$env:DATABASE_URL = $env:TEST_DATABASE_URL

Step "docker_pg_up" {
  docker compose -f (Join-Path $Root "infra\postgres-test\compose.yaml") up -d
  $deadline = (Get-Date).AddSeconds(90)
  do {
    $h = docker inspect --format='{{.State.Health.Status}}' kwzy_party_test_pg 2>$null
    if ($h -eq "healthy") { "healthy"; return }
    Start-Sleep 2
  } while ((Get-Date) -lt $deadline)
  throw "pg not healthy"
}

Step "alembic_upgrade" {
  Push-Location $Api
  & $Py -c "from app.core.config import get_settings; get_settings.cache_clear()"
  & (Join-Path $Api ".venv\Scripts\alembic.exe") upgrade head
  & (Join-Path $Api ".venv\Scripts\alembic.exe") heads
  Pop-Location
}

Step "pytest_full" {
  Push-Location $Api
  & $Py -m pytest -q --tb=line
  Pop-Location
}

Step "etl_generate_and_pg" {
  & $Py (Join-Path $Root "tools\etl\generate_large_fixture.py") --out (Join-Path $Root "tools\etl\fixtures\large_legacy.json")
  & $Py (Join-Path $Root "tools\etl\apply_to_postgres.py") --fixture (Join-Path $Root "tools\etl\fixtures\large_legacy.json")
  & $Py (Join-Path $Root "tools\etl\apply_to_postgres.py") --fixture (Join-Path $Root "tools\etl\fixtures\large_legacy.json") --no-reset-schema
}

Step "frontend_build" {
  Push-Location $Web
  npm run build
  Pop-Location
}

# API smoke process
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
  Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
$env:APP_ENV = "local"
$env:ALLOW_ANON_DEV = "false"
$env:JWT_SECRET = "local-staging-jwt-secret-not-for-production-32"
$env:LOCAL_ADMIN_PASSWORD = "admin123"
$env:DATABASE_URL = "sqlite+pysqlite:///$($Api.Replace('\','/'))/local_staging.db"
$proc = Start-Process -FilePath $Py -ArgumentList @("-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000") -WorkingDirectory $Api -PassThru -WindowStyle Hidden
try {
  Step "http_health" {
    $ok = $false
    for ($i=0; $i -lt 60; $i++) {
      Start-Sleep 1
      try {
        $h = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 2
        if ($h.status -eq "up") { $h | ConvertTo-Json -Compress; $ok=$true; break }
      } catch {}
    }
    if (-not $ok) { throw "health timeout" }
  }
  Step "http_login" {
    $body = @{ username = "admin"; password = "admin123" } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/auth/login" -Method Post -Body $body -ContentType "application/json"
    if (-not $r.data.access_token) { throw "no token" }
    "token_len=$($r.data.access_token.Length)"
  }
}
finally {
  if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
}

$path = Join-Path $ReportDir ("acceptance_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
$report | ConvertTo-Json -Depth 6 | Set-Content $path -Encoding utf8
Write-Output "REPORT=$path"
$failed = @($report | Where-Object { $_.exit_code -ne 0 })
if ($failed.Count -gt 0) {
  Write-Output "KWZY_LOCAL_STAGING_EQUIVALENT=FAIL"
  exit 1
}
Write-Output "KWZY_LOCAL_STAGING_EQUIVALENT=PASS"
Write-Output "KWZY_DATA_MIGRATION_READINESS=READY_FOR_STAGING_DATA"
exit 0
