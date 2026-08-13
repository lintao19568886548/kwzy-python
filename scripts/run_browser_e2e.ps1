# One-shot browser E2E acceptance: Playwright globalSetup owns PG16 + API + FE.
# Exit non-zero on any failure; never skip business steps when stack is down.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "apps\web\package.json"))) {
  $Root = $PSScriptRoot
  if (-not (Test-Path (Join-Path $Root "apps\web\package.json"))) {
    # scripts/ is under repo root
    $Root = Split-Path -Parent $PSScriptRoot
  }
}
$Web = Join-Path $Root "apps\web"
$LogDir = Join-Path $Web "test-results\acceptance-logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Report = Join-Path $LogDir "browser-e2e-$Stamp.json"

$started = Get-Date
Write-Host "=== KWZY Browser E2E Acceptance ==="
Write-Host "start: $started"
Write-Host "web: $Web"

Push-Location $Web
try {
  if (-not (Test-Path "node_modules")) {
    npm ci
  }
  npx playwright install chromium
  $env:E2E_CLEAN_DOCKER = if ($env:E2E_CLEAN_DOCKER) { $env:E2E_CLEAN_DOCKER } else { "0" }
  npm run test:e2e -- --reporter=list
  $code = $LASTEXITCODE
} finally {
  Pop-Location
}
$ended = Get-Date
$result = [ordered]@{
  command = "npm run test:e2e"
  started_at = $started.ToString("o")
  ended_at = $ended.ToString("o")
  exit_code = $code
  log_dir = $LogDir
  playwright_report = (Join-Path $Web "playwright-report")
  evidence = (Join-Path $Web "test-results")
}
$result | ConvertTo-Json | Set-Content -Path $Report -Encoding UTF8
Write-Host "end: $ended exit=$code report=$Report"
exit $code
