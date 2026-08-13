# Full local staging acceptance: PG16 + Alembic + pytest + ETL + FE prod + Playwright E2E.
# Any mandatory step failure => non-zero exit.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $Root "apps\api"))) {
  $Root = "D:\重构python\kwzy-python"
}
$Api = Join-Path $Root "apps\api"
$Web = Join-Path $Root "apps\web"
$Py = Join-Path $Api ".venv\Scripts\python.exe"
$ReportDir = Join-Path $Root "infra\local-staging\out"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$report = @()
$globalStart = Get-Date

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
  if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { $code = $LASTEXITCODE }
  $entry = [ordered]@{
    step = $name
    exit_code = $code
    ms = $sw.ElapsedMilliseconds
    started = (Get-Date).ToString("o")
    output_tail = ($out.Trim() -split "`n" | Select-Object -Last 12) -join "`n"
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
$env:JWT_SECRET = "local-staging-jwt-secret-not-for-production-32"
$env:LOCAL_ADMIN_PASSWORD = "admin123"
$env:ALLOW_ANON_DEV = "false"
$env:APP_ENV = "local"
$env:SMS_PROVIDER = "fake"
$env:OSS_PROVIDER = "local"

try {
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

  Step "alembic_down_up" {
    Push-Location $Api
    & (Join-Path $Api ".venv\Scripts\alembic.exe") downgrade -1
    & (Join-Path $Api ".venv\Scripts\alembic.exe") upgrade head
    Pop-Location
  }

  Step "pytest_full" {
    Push-Location $Api
    & $Py -m pytest -q --tb=line
    Pop-Location
  }

  Step "etl_fast" {
    & $Py (Join-Path $Root "tools\etl\run_etl_drill.py") --profile fast --seed 42 --out-dir (Join-Path $ReportDir "etl_fast")
  }

  Step "etl_acceptance" {
    & $Py (Join-Path $Root "tools\etl\run_etl_drill.py") --profile acceptance --seed 42 --out-dir (Join-Path $ReportDir "etl_acceptance")
  }

  Step "frontend_lint" {
    Push-Location $Web
    npm run lint
    Pop-Location
  }

  Step "frontend_typecheck" {
    Push-Location $Web
    npm run typecheck
    Pop-Location
  }

  Step "frontend_unit" {
    Push-Location $Web
    npm run test:unit
    Pop-Location
  }

  Step "frontend_build" {
    Push-Location $Web
    $env:VITE_API_BASE = "http://127.0.0.1:8010/api/v1"
    npm run build
    Pop-Location
  }

  Step "playwright_browser_e2e" {
    Push-Location $Web
    npx playwright test
    Pop-Location
  }

  Step "git_diff_check" {
    Push-Location $Root
    git diff --check
    Pop-Location
  }
}
catch {
  Write-Output "ACCEPTANCE_ERROR=$_"
}

$globalEnd = Get-Date
$path = Join-Path $ReportDir ("acceptance_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
$summary = [ordered]@{
  started_at = $globalStart.ToString("o")
  ended_at = $globalEnd.ToString("o")
  steps = $report
  playwright_report = (Join-Path $Web "playwright-report")
  test_results = (Join-Path $Web "test-results")
  etl_fast = (Join-Path $ReportDir "etl_fast")
  etl_acceptance = (Join-Path $ReportDir "etl_acceptance")
}
$summary | ConvertTo-Json -Depth 8 | Set-Content $path -Encoding utf8
Write-Output "REPORT=$path"
$failed = @($report | Where-Object { $_.exit_code -ne 0 })
if ($failed.Count -gt 0) {
  Write-Output "KWZY_LOCAL_STAGING_EQUIVALENT=FAIL"
  Write-Output ("FAILED_STEPS=" + (($failed | ForEach-Object { $_.step }) -join ","))
  exit 1
}
Write-Output "KWZY_LOCAL_STAGING_EQUIVALENT=PASS"
Write-Output "KWZY_DATA_MIGRATION_READINESS=READY_FOR_STAGING_DATA"
Write-Output "KWZY_FULL_FRONTEND_REPLACEMENT=COMPLETE"
exit 0
