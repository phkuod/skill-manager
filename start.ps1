<#
.SYNOPSIS
    Start the Skill Market service on Windows PowerShell.
.DESCRIPTION
    Mimics start.sh logic exactly to load environment variables, collect static files,
    and launch the server in the selected mode.
.PARAMETER Mode
    Deployment mode: dev, development, prod, or production. Defaults to development.
.EXAMPLE
    .\start.ps1
.EXAMPLE
    .\start.ps1 prod
#>

param (
    [string]$Mode = "development"
)

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
if (-not $Root) {
    $Root = (Get-Item .).FullName
}

# Normalize short aliases: dev → development, prod → production
if ($Mode -eq "dev") { $Mode = "development" }
elseif ($Mode -eq "prod") { $Mode = "production" }

# ── Load env file for the selected mode ───────────────────────────────────────
$EnvFile = Join-Path $Root ".env.$Mode"
if (Test-Path $EnvFile) {
    Write-Host "[start] Loading $EnvFile" -ForegroundColor Cyan
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            if ($line -match '^([^=]+)=(.*)$') {
                $key = $Matches[1].Trim()
                $val = $Matches[2].Trim()
                # Strip outer quotes if present
                if ($val -match '^"(.*)"$' -or $val -match "^'(.*)'$") {
                    $val = $Matches[1]
                }
                [Environment]::SetEnvironmentVariable($key, $val)
            }
        }
    }
}

# ── Pick a Python interpreter ─────────────────────────────────────────────────
$Py = ""
$WinPy = Join-Path $Root "venv\Scripts\python.exe"
$UnixPy = Join-Path $Root "venv\bin\python"

if (Test-Path $WinPy) {
    $Py = $WinPy
}
elseif (Test-Path $UnixPy) {
    $Py = $UnixPy
}
else {
    $Py = "python"
}

# ── Collect static files (idempotent) ─────────────────────────────────────────
Write-Host "[start] Collecting static files..." -ForegroundColor Cyan
& $Py (Join-Path $Root "manage.py") collectstatic --noinput -v 0

# ── Launch ────────────────────────────────────────────────────────────────────
$Port = [Environment]::GetEnvironmentVariable("PORT")
if (-not $Port) {
    $Port = "3000"
}

$SkillRepoPath = [Environment]::GetEnvironmentVariable("SKILL_REPO_PATH")
if (-not $SkillRepoPath) {
    [Environment]::SetEnvironmentVariable("SKILL_REPO_PATH", (Join-Path $Root "skill_repo"))
}

if ($Mode -eq "production") {
    Write-Host "[start] Starting gunicorn (production) on :$Port ..." -ForegroundColor Cyan
    [Environment]::SetEnvironmentVariable("DJANGO_SETTINGS_MODULE", "skill_market.settings")
    
    $DebugEnv = [Environment]::GetEnvironmentVariable("DEBUG")
    if (-not $DebugEnv) {
        [Environment]::SetEnvironmentVariable("DEBUG", "False")
    }
    
    $AllowedHosts = [Environment]::GetEnvironmentVariable("ALLOWED_HOSTS")
    if (-not $AllowedHosts) {
        [Environment]::SetEnvironmentVariable("ALLOWED_HOSTS", "localhost,127.0.0.1")
    }
    
    # Check if gunicorn executable exists in venv
    $GunicornExe = Join-Path $Root "venv\Scripts\gunicorn.exe"
    if (Test-Path $GunicornExe) {
        & $GunicornExe skill_market.wsgi --bind "127.0.0.1:$Port" --workers 1 --chdir "$Root"
    }
    else {
        gunicorn skill_market.wsgi --bind "127.0.0.1:$Port" --workers 1 --chdir "$Root"
    }
}
else {
    Write-Host "[start] Starting Django dev server on :$Port ..." -ForegroundColor Cyan
    & $Py (Join-Path $Root "manage.py") runserver "127.0.0.1:$Port"
}
