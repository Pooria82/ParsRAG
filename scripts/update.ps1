# Update ParsRAG to the latest release, after backing up its data.
#
# Run from anywhere inside the ParsRAG folder:
#   powershell -ExecutionPolicy Bypass -File scripts/update.ps1
#
# Steps: check the copy is clean, find the latest release tag, back up the
# server data (documents index and settings) and .env, switch the code to that
# release (skipping any versions in between), rebuild and restart with the
# same Compose files, and wait until the service is ready. If the rebuild
# fails, the previous version is started again. Works with Windows PowerShell 5.1.

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Fail([string]$Message) {
    Write-Host "ParsRAG update stopped: $Message" -ForegroundColor Red
    exit 1
}

function Run([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command $($Arguments -join ' ') failed" }
}

foreach ($tool in @('git', 'docker')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Fail "$tool is not installed or not on PATH." }
}
if (-not (Test-Path (Join-Path $Root '.git'))) { Fail 'this folder is not a git clone of ParsRAG; download the new release by hand.' }

$changed = git status --porcelain --untracked-files=no
if ($changed) { Fail 'files in this copy were changed. Commit or undo them first (git status shows them).' }

$branch = git symbolic-ref -q --short HEAD
if ($branch -and $branch -ne 'main') { Fail "this copy follows the '$branch' branch. Switch to main (git switch main) or update by hand." }

Write-Host 'Looking for the latest release...'
Run 'git' @('fetch', '--quiet', '--tags', 'origin')
$latest = git tag -l 'v*' --sort=-v:refname | Where-Object { $_ -match '^v\d+\.\d+\.\d+$' } | Select-Object -First 1
if (-not $latest) { Fail 'no release tags were found.' }
$current = (Get-Content (Join-Path $Root 'VERSION') -Raw).Trim()
if ("v$current" -eq $latest) {
    Write-Host "ParsRAG $current is already the latest release." -ForegroundColor Green
    exit 0
}
Write-Host "Updating ParsRAG $current to $($latest.TrimStart('v'))."

# Reuse the Compose files and profile the running stack was started with.
$composeArgs = @()
$app = docker compose ps -q app 2>$null
$project = 'parsrag'
$image = $null
if ($app) {
    $files = docker inspect $app --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'
    foreach ($file in ($files -split ',')) { if ($file) { $composeArgs += @('-f', $file) } }
    $project = docker inspect $app --format '{{index .Config.Labels "com.docker.compose.project"}}'
    $image = docker inspect $app --format '{{.Config.Image}}'
    $ollama = docker compose @composeArgs ps -q ollama 2>$null
    if ($ollama) { $composeArgs += @('--profile', 'local-model') }
}

# Back up before anything changes.
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path (Join-Path $Root 'backups') "$stamp-v$current"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
if (Test-Path (Join-Path $Root '.env')) { Copy-Item (Join-Path $Root '.env') (Join-Path $backup 'env.backup') }
$volumes = @("$($project)_qdrant_data", "$($project)_app_config") | Where-Object {
    docker volume inspect $_ 2>$null | Out-Null
    $LASTEXITCODE -eq 0
}
if ($volumes) {
    if (-not $image) { $image = 'qdrant/qdrant:v1.19.1' }
    Write-Host 'Backing up the documents index and settings (the service stops for a moment)...'
    Run 'docker' (@('compose') + $composeArgs + @('stop', 'app', 'qdrant'))
    try {
        foreach ($volume in $volumes) {
            Run 'docker' @('run', '--rm', '--user', '0', '--entrypoint', 'tar', '-v', "$($volume):/data:ro", '-v', "$($backup):/backup", $image, '-czf', "/backup/$volume.tar.gz", '-C', '/data', '.')
        }
    } catch {
        docker compose @composeArgs up -d | Out-Null
        Fail "the backup failed, so nothing was updated. ($_)"
    }
}
@"
ParsRAG $current backup, $stamp.
To go back: git checkout v$current, then restore each volume with
  docker run --rm --user 0 --entrypoint tar -v <volume>:/data -v <this folder>:/backup <image> -xzf /backup/<volume>.tar.gz -C /data
and start ParsRAG again. Conversations live in the browser: use the backup
file the app downloaded before this update (Settings > Data > Import).
"@ | Set-Content -Encoding utf8 (Join-Path $backup 'RESTORE.txt')
Write-Host "Backup saved in $backup" -ForegroundColor Green

$previous = git rev-parse HEAD
try {
    if ($branch -eq 'main') { Run 'git' @('pull', '--quiet', '--ff-only', 'origin', 'main') }
    else { Run 'git' @('checkout', '--quiet', $latest) }
    Write-Host 'Building and starting the new version (this can take several minutes)...'
    Run 'docker' (@('compose') + $composeArgs + @('up', '-d', '--build'))
} catch {
    Write-Host "The update failed: $_" -ForegroundColor Red
    Write-Host 'Starting the previous version again...'
    git checkout --quiet $previous
    docker compose @composeArgs up -d --build
    Fail "the previous version ($current) is running again. Your backup is in $backup"
}

$address = (docker compose @composeArgs port app 8000) -replace '^0\.0\.0\.0', '127.0.0.1'
if (-not $address) { $address = '127.0.0.1:8000' }
Write-Host "Waiting for ParsRAG at http://$address ..."
$deadline = (Get-Date).AddMinutes(10)
while ((Get-Date) -lt $deadline) {
    try {
        $ready = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://$address/health/ready"
        if ($ready.StatusCode -eq 200) {
            Write-Host "ParsRAG $($latest.TrimStart('v')) is ready: http://$address" -ForegroundColor Green
            Write-Host 'Reload the page in the browser; it shows what changed.'
            exit 0
        }
    } catch { Start-Sleep -Seconds 5 }
}
Write-Host "ParsRAG $($latest.TrimStart('v')) started but is not ready yet; check: docker compose logs app" -ForegroundColor Yellow
