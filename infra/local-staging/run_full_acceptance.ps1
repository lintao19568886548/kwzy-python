# Full local staging acceptance from clean-ish state.
# Any mandatory step failure => non-zero exit. Do not swallow failures.
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $Root "apps\api"))) {
  $Root = "D:\重构python\kwzy-python"
}
$Api = Join-Path $Root "apps\api"
$Web = Join-Path $Root "apps\web"
$Py = Join-Path $Api ".venv\Scripts\python.exe"
$Alembic = Join-Path $Api ".venv\Scripts\alembic.exe"
$ReportDir = Join-Path $Root "infra\local-staging\out"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$report = @()
$globalStart = Get-Date
$composeFile = Join-Path $Root "infra\postgres-test\compose.yaml"
$pgEnvFile = Join-Path $Root "infra\postgres-test\.env"
if (-not (Test-Path -LiteralPath $pgEnvFile)) {
  throw "missing gitignored local test database env: $pgEnvFile"
}
$pgSettings = @{}
foreach ($line in Get-Content -LiteralPath $pgEnvFile) {
  $trimmed = $line.Trim()
  if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
  $pair = $trimmed.Split("=", 2)
  $pgSettings[$pair[0].Trim()] = $pair[1].Trim()
}
$pgUser = [string]$pgSettings["POSTGRES_USER"]
$pgPassword = [string]$pgSettings["POSTGRES_PASSWORD"]
$pgDatabase = [string]$pgSettings["POSTGRES_DB"]
$pgPort = [string]$pgSettings["POSTGRES_PORT"]
if (-not $pgUser -or -not $pgPassword -or -not $pgDatabase -or -not $pgPort) {
  throw "local PostgreSQL .env is missing a required POSTGRES_* value"
}
$pgUrl = "postgresql+psycopg://$([uri]::EscapeDataString($pgUser)):$([uri]::EscapeDataString($pgPassword))@127.0.0.1:$pgPort/$pgDatabase"

function Step($name, $scriptBlock) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $code = 0
  $captured = [System.Collections.Generic.List[string]]::new()
  $global:LASTEXITCODE = 0
  try {
    & $scriptBlock 2>&1 | ForEach-Object { $captured.Add("$_") }
  } catch {
    $code = 1
    $captured.Add("$_")
  }
  $out = $captured -join "`n"
  $sw.Stop()
  if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { $code = $LASTEXITCODE }
  $entry = [ordered]@{
    step = $name
    exit_code = $code
    ms = $sw.ElapsedMilliseconds
    started = (Get-Date).ToString("o")
    output_tail = ($out.Trim() -split "`n" | Select-Object -Last 20) -join "`n"
  }
  $script:report += $entry
  Write-Output ("STEP={0} EXIT={1} MS={2}" -f $name, $code, $sw.ElapsedMilliseconds)
  if ($code -ne 0) { throw "step failed: $name" }
  return $out
}

function Assert-NativeSuccess($label) {
  if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "$label failed with exit code $LASTEXITCODE"
  }
}

function Assert-AlembicSingleCurrentHead {
  $heads = @(& $Alembic heads)
  Assert-NativeSuccess "alembic heads"
  $headLines = @($heads | Where-Object { $_.Trim() })
  if ($headLines.Count -ne 1 -or $headLines[0] -notmatch '^([0-9a-z]+)\s+\(head\)$') {
    throw "expected exactly one Alembic head, got: $($headLines -join '; ')"
  }
  $headRevision = $Matches[1]

  $current = @(& $Alembic current)
  Assert-NativeSuccess "alembic current"
  $currentLines = @($current | Where-Object { $_.Trim() })
  $expected = '^' + [regex]::Escape($headRevision) + '\s+\(head\)$'
  if ($currentLines.Count -ne 1 -or $currentLines[0] -notmatch $expected) {
    throw "Alembic current does not equal the unique head ${headRevision}: $($currentLines -join '; ')"
  }
  "ALEMBIC_UNIQUE_CURRENT_HEAD=PASS revision=$headRevision"
}

$env:POSTGRES_PASSWORD = $pgPassword
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:TEST_DATABASE_URL = $pgUrl
$env:POSTGRES_TEST_URL = $pgUrl
$env:ETL_DATABASE_URL = $pgUrl
$env:DATABASE_URL = $pgUrl
$env:JWT_SECRET = "local-staging-jwt-secret-not-for-production-32"
$env:LOCAL_ADMIN_PASSWORD = "admin123"
$env:ALLOW_ANON_DEV = "false"
$env:APP_ENV = "local"
$env:DEBUG = "false"
$env:SMS_PROVIDER = "fake"
$env:OSS_PROVIDER = "local"

try {
  Step "docker_clean_start" {
    docker compose -f $composeFile down -v
    "cleaned"
  }

  Step "docker_pg_up" {
    docker compose -f $composeFile up -d
    Assert-NativeSuccess "docker compose up"
    $deadline = (Get-Date).AddSeconds(120)
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
    & $Alembic upgrade head
    Assert-NativeSuccess "alembic upgrade head"
    Assert-AlembicSingleCurrentHead
    Pop-Location
  }

  Step "alembic_down_up" {
    Push-Location $Api
    & $Alembic downgrade -1
    Assert-NativeSuccess "alembic downgrade -1"
    & $Alembic upgrade head
    Assert-NativeSuccess "alembic re-upgrade head"
    Assert-AlembicSingleCurrentHead
    Pop-Location
  }

  Step "backend_ruff_error_rules" {
    # The legacy tree still has style-modernization findings. Error-level Ruff
    # rules are a hard gate for every backend module and test.
    Push-Location $Api
    & $Py -m ruff check --select E4,E7,E9,F app tests
    Assert-NativeSuccess "backend Ruff error rules"
    Pop-Location
  }

  Step "pytest_non_pg_and_pg" {
    # Full suite with TEST_DATABASE_URL set => PG paths + sqlite-less paths as configured
    Push-Location $Api
    & $Py -m pytest -q --tb=line
    Pop-Location
  }

  Step "workbench_worker_once" {
    Push-Location $Api
    & $Py -m app.workers.workbench --once --batch-size 100
    Pop-Location
  }

  Step "etl_fast" {
    & $Py (Join-Path $Root "tools\etl\run_etl_drill.py") --profile fast --seed 42 --out-dir (Join-Path $ReportDir "etl_fast")
  }

  Step "etl_acceptance" {
    & $Py (Join-Path $Root "tools\etl\run_etl_drill.py") --profile acceptance --seed 42 --out-dir (Join-Path $ReportDir "etl_acceptance")
  }

  Step "identity_etl_acceptance" {
    $identityReport = Join-Path $ReportDir "identity_etl\identity_etl.json"
    & $Py (Join-Path $Root "tools\etl\run_identity_etl_drill.py") --database-url $pgUrl --out $identityReport
  }

  Step "asset_etl_acceptance" {
    $assetReport = Join-Path $ReportDir "asset_etl\asset_etl.json"
    & $Py (Join-Path $Root "tools\etl\run_asset_etl_drill.py") --database-url $pgUrl --out $assetReport
  }

  Step "asset_portfolio_etl_acceptance" {
    $assetPortfolioReport = Join-Path $ReportDir "asset_portfolio_etl\asset-portfolio-etl.json"
    & $Py (Join-Path $Root "tools\etl\run_asset_portfolio_etl_drill.py") --database-url $pgUrl --out $assetPortfolioReport
  }

  Step "crm_etl_acceptance" {
    $crmReport = Join-Path $ReportDir "crm_etl\crm_etl.json"
    & $Py (Join-Path $Root "tools\etl\run_crm_etl_drill.py") --database-url $pgUrl --out $crmReport
  }

  Step "contract_etl_acceptance" {
    $contractReport = Join-Path $ReportDir "contract_etl\contract_etl.json"
    & $Py (Join-Path $Root "tools\etl\run_contract_etl_drill.py") --database-url $pgUrl --out $contractReport
  }

  Step "organization_governance_etl_acceptance" {
    $organizationGovernanceReport = Join-Path $ReportDir "organization_governance_etl\organization_governance_etl.json"
    & $Py (Join-Path $Root "tools\etl\run_organization_governance_etl_drill.py") --database-url $pgUrl --out $organizationGovernanceReport
  }

  Step "approval_audit_etl_acceptance" {
    $approvalAuditReport = Join-Path $ReportDir "approval_audit_etl\approval_audit_etl.json"
    & $Py (Join-Path $Root "tools\etl\run_approval_audit_etl_drill.py") --database-url $pgUrl --out $approvalAuditReport
  }

  Step "workbench_automation_etl_acceptance" {
    $workbenchAutomationReport = Join-Path $ReportDir "workbench_automation_etl\workbench-automation-etl.json"
    & $Py (Join-Path $Root "tools\etl\run_workbench_automation_etl_drill.py") --database-url $pgUrl --out $workbenchAutomationReport
  }

  Step "http_performance_seed" {
    & $Py (Join-Path $Root "scripts\e2e_seed.py")
  }

  Step "http_performance_gate" {
    $perfDir = Join-Path $ReportDir "performance"
    New-Item -ItemType Directory -Force -Path $perfDir | Out-Null
    $stdout = Join-Path $perfDir "api.stdout.log"
    $stderr = Join-Path $perfDir "api.stderr.log"
    $apiProc = $null
    try {
      Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
      }
      $apiProc = Start-Process -FilePath $Py `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8010") `
        -WorkingDirectory $Api -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
      $deadline = (Get-Date).AddSeconds(120)
      do {
        try {
          $ready = Invoke-RestMethod -Uri "http://127.0.0.1:8010/health/ready" -TimeoutSec 2
          if ($ready.status -eq "ready") { break }
        } catch {}
        Start-Sleep 1
      } while ((Get-Date) -lt $deadline)
      if ((Get-Date) -ge $deadline) { throw "performance API readiness timeout" }
      $env:PERF_USERNAME = "admin"
      $env:PERF_PASSWORD = "admin123"
      & $Py (Join-Path $Root "scripts\http_performance_gate.py") `
        --base-url "http://127.0.0.1:8010/api/v1" `
        --requests 1000 --concurrency 25 --warmup 40 `
        --max-p95-ms 500 --max-error-rate-percent 1 --min-rps 20 `
        --output (Join-Path $perfDir "http-performance.json")
      Assert-NativeSuccess "HTTP performance gate"
      & $Py (Join-Path $Root "scripts\approval_audit_http_journey.py") `
        --base-url "http://127.0.0.1:8010/api/v1" `
        --username "admin" --password "admin123" `
        --output (Join-Path $perfDir "approval-audit-http-journey.json")
      Assert-NativeSuccess "approval audit HTTP journey"
      & $Py (Join-Path $Root "scripts\workbench_automation_http_journey.py") `
        --base-url "http://127.0.0.1:8010/api/v1" `
        --username "admin" --password "admin123" `
        --output (Join-Path $perfDir "workbench-automation-http-journey.json")
      Assert-NativeSuccess "workbench automation HTTP journey"
      & $Py (Join-Path $Root "scripts\asset_portfolio_http_journey.py") `
        --base-url "http://127.0.0.1:8010/api/v1" `
        --username "admin" --password "admin123" `
        --output (Join-Path $perfDir "asset-portfolio-http-journey.json")
      Assert-NativeSuccess "asset portfolio HTTP journey"
    } finally {
      Remove-Item Env:PERF_PASSWORD -ErrorAction SilentlyContinue
      if ($apiProc -and -not $apiProc.HasExited) {
        Stop-Process -Id $apiProc.Id -Force -ErrorAction SilentlyContinue
      }
    }
  }

  Step "backup_restore" {
    $bakDir = Join-Path $ReportDir "backup"
    New-Item -ItemType Directory -Force -Path $bakDir | Out-Null
    $dump = Join-Path $bakDir "kwzy_party_test.dump"
    docker exec kwzy_party_test_pg pg_dump -U kwzy_party_test -d kwzy_party_test -Fc -f /tmp/kwzy.dump
    Assert-NativeSuccess "pg_dump"
    docker cp kwzy_party_test_pg:/tmp/kwzy.dump $dump
    Assert-NativeSuccess "docker copy dump"
    if (-not (Test-Path $dump)) { throw "dump missing" }
    $size = (Get-Item $dump).Length
    if ($size -lt 1000) { throw "dump too small: $size" }
    # restore into a temp database
    docker exec kwzy_party_test_pg psql -U kwzy_party_test -d postgres -c "DROP DATABASE IF EXISTS kwzy_restore_check;"
    Assert-NativeSuccess "drop restore database"
    docker exec kwzy_party_test_pg psql -U kwzy_party_test -d postgres -c "CREATE DATABASE kwzy_restore_check OWNER kwzy_party_test;"
    Assert-NativeSuccess "create restore database"
    docker cp $dump kwzy_party_test_pg:/tmp/kwzy_restore.dump
    Assert-NativeSuccess "docker copy restore dump"
    docker exec kwzy_party_test_pg pg_restore -U kwzy_party_test -d kwzy_restore_check --clean --if-exists /tmp/kwzy_restore.dump
    Assert-NativeSuccess "pg_restore"
    $cnt = docker exec kwzy_party_test_pg psql -U kwzy_party_test -d kwzy_restore_check -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
    Assert-NativeSuccess "restore verification query"
    if ([int]$cnt -lt 5) { throw "restore table count too low: $cnt" }
    docker exec kwzy_party_test_pg psql -U kwzy_party_test -d postgres -c "DROP DATABASE IF EXISTS kwzy_restore_check;"
    "BACKUP_RESTORE=PASS dump_bytes=$size restored_tables=$cnt"
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

  Step "openapi_strict" {
    Push-Location $Api
    & $Py -m pytest tests/test_openapi_contract.py -q --tb=line
    Assert-NativeSuccess "OpenAPI contract tests"
    $yaml = Join-Path $Root "docs\04-api\openapi-v1-core.yaml"
    & $Py -c @"
from pathlib import Path
from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename
spec, _ = read_from_filename(r'$yaml')
validate(spec)
print('OPENAPI_YAML_STRICT=PASS')
"@
    Pop-Location
  }

  Step "openspec_strict" {
    Push-Location $Root
    openspec validate --all --strict --no-interactive
    Pop-Location
  }

  Step "secrets_scan" {
    Push-Location $Root
    $patterns = @(
      'BEGIN RSA PRIVATE KEY',
      'BEGIN OPENSSH PRIVATE KEY',
      'AKIA[0-9A-Z]{16}',
      'password\s*=\s*["''](?!admin123|kwzy_test|x|changeme)[^"'']{8,}'
    )
    $hits = @()
    # Include newly created, non-ignored files as well as tracked files. A
    # pre-commit acceptance run must not leave its newest code outside the scan.
    $files = git ls-files --cached --others --exclude-standard
    foreach ($f in $files) {
      if ($f -match '\.(png|jpg|jpeg|gif|webp|ico|woff2?|pdf|zip|gz)$') { continue }
      if (-not (Test-Path $f)) { continue }
      $text = Get-Content -LiteralPath $f -Raw -ErrorAction SilentlyContinue
      if (-not $text) { continue }
      foreach ($p in $patterns) {
        if ($text -match $p) {
          # allow known test-only fixtures
          if ($f -match 'test|fixture|e2e|local-staging|compose\.yaml|README|docs/') { continue }
          $hits += "$f :: $p"
        }
      }
    }
    if ($hits.Count -gt 0) {
      $hits | ForEach-Object { $_ }
      throw "secrets_scan found hits: $($hits.Count)"
    }
    "SECRETS_SCAN=PASS files_scanned=$($files.Count)"
  }

  Step "git_diff_check" {
    Push-Location $Root
    git diff --check
    Pop-Location
  }

  Step "cleanup_test_resources" {
    # stop e2e leftover ports
    # E2E owns only 8010 (API) and 4173 (web). Never stop an arbitrary service
    # on the developer's conventional port 8000.
    foreach ($port in 8010, 4173) {
      Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
      }
    }
    docker compose -f $composeFile down -v
    "CLEANUP=PASS"
  }
}
catch {
  Write-Output "ACCEPTANCE_ERROR=$_"
  # best-effort cleanup on failure
  try { docker compose -f $composeFile down -v | Out-Null } catch {}
}

$globalEnd = Get-Date
$path = Join-Path $ReportDir ("acceptance_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
$summary = [ordered]@{
  started_at = $globalStart.ToString("o")
  ended_at = $globalEnd.ToString("o")
  duration_ms = [int]($globalEnd - $globalStart).TotalMilliseconds
  head = (git -C $Root rev-parse HEAD)
  steps = $report
  playwright_report = (Join-Path $Web "playwright-report")
  test_results = (Join-Path $Web "test-results")
  etl_fast = (Join-Path $ReportDir "etl_fast")
  etl_acceptance = (Join-Path $ReportDir "etl_acceptance")
  identity_etl = (Join-Path $ReportDir "identity_etl\identity_etl.json")
  asset_etl = (Join-Path $ReportDir "asset_etl\asset_etl.json")
  asset_portfolio_etl = (Join-Path $ReportDir "asset_portfolio_etl\asset-portfolio-etl.json")
  crm_etl = (Join-Path $ReportDir "crm_etl\crm_etl.json")
  contract_etl = (Join-Path $ReportDir "contract_etl\contract_etl.json")
  organization_governance_etl = (Join-Path $ReportDir "organization_governance_etl\organization_governance_etl.json")
  approval_audit_etl = (Join-Path $ReportDir "approval_audit_etl\approval_audit_etl.json")
  workbench_automation_etl = (Join-Path $ReportDir "workbench_automation_etl\workbench-automation-etl.json")
  http_performance = (Join-Path $ReportDir "performance\http-performance.json")
  approval_audit_http = (Join-Path $ReportDir "performance\approval-audit-http-journey.json")
  workbench_automation_http = (Join-Path $ReportDir "performance\workbench-automation-http-journey.json")
  asset_portfolio_http = (Join-Path $ReportDir "performance\asset-portfolio-http-journey.json")
  backup = (Join-Path $ReportDir "backup")
}
$summary | ConvertTo-Json -Depth 8 | Set-Content $path -Encoding utf8
Write-Output "REPORT=$path"
$failed = @($report | Where-Object { $_.exit_code -ne 0 })
if ($failed.Count -gt 0 -or $report.Count -eq 0) {
  Write-Output "KWZY_LOCAL_STAGING_EQUIVALENT=FAIL"
  Write-Output ("FAILED_STEPS=" + (($failed | ForEach-Object { $_.step }) -join ","))
  exit 1
}
Write-Output "KWZY_IMPLEMENTED_SCOPE_LOCAL_ACCEPTANCE=PASS"
Write-Output "KWZY_DATA_MIGRATION_READINESS=CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA"
Write-Output "KWZY_PC_CORE_SLICE_ACCEPTANCE=PASS"
Write-Output "KWZY_FULL_FRONTEND_REPLACEMENT=BLOCKED_MOBILE_AND_MINIPROGRAM_NOT_IMPLEMENTED"
exit 0
