# Local staging equivalent smoke (HTTP). Does not claim REMOTE_STAGING.
$ErrorActionPreference = "Stop"
$base = $env:LOCAL_STAGING_API
if (-not $base) { $base = "http://127.0.0.1:8000" }
Write-Output "SMOKE base=$base"
$h = Invoke-RestMethod -Uri "$base/health" -Method Get
if ($h.status -ne "up") { throw "health failed" }
Write-Output "HEALTH=OK version=$($h.version)"
Write-Output "LOCAL_STAGING_EQUIVALENT_SMOKE=PASS"
