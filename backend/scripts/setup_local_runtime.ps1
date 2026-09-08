[CmdletBinding()]
param(
    [string]$Server = 'localhost',
    [int]$Port = 5432,
    [string]$Database = 'sih26162',
    [string]$Username = 'postgres',
    [string]$Password = $env:POSTGRES_PASSWORD,
    [string]$FirmsMapKey = $env:FIRMS_MAP_KEY,
    [string]$DataThrough = (Get-Date -Format 'yyyy-MM-dd'),
    [string]$PythonExe,
    [switch]$Replace,
    [switch]$Resume,
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$previousPythonPath = $env:PYTHONPATH

if ($Replace -and $Resume) { throw 'Use either -Replace or -Resume, not both.' }
if ($Database -notmatch '^[A-Za-z][A-Za-z0-9_]{0,62}$') {
    throw 'Database must be a simple PostgreSQL identifier.'
}
try { [void][datetime]::ParseExact($DataThrough, 'yyyy-MM-dd', $null) }
catch { throw 'DataThrough must use YYYY-MM-DD.' }

function Resolve-PostgresTool([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $installRoot = 'C:\Program Files\PostgreSQL'
    if (Test-Path -LiteralPath $installRoot) {
        $candidate = Get-ChildItem -LiteralPath $installRoot -Directory |
            Sort-Object { try { [version]$_.Name } catch { [version]'0.0' } } -Descending |
            ForEach-Object { Join-Path $_.FullName "bin\$Name.exe" } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1
        if ($candidate) { return $candidate }
    }
    throw "Could not find $Name. Install PostgreSQL client tools or add its bin directory to PATH."
}

function Read-PlainSecret([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}

function Test-Python([string]$Candidate) {
    if (-not $Candidate -or -not (Test-Path -LiteralPath $Candidate)) { return $false }
    & $Candidate -c "import sys; assert sys.version_info[:2] == (3, 11)" 2>$null
    return $LASTEXITCODE -eq 0
}

function Resolve-Python311 {
    if ($PythonExe) {
        $candidate = (Resolve-Path -LiteralPath $PythonExe).Path
        if (-not (Test-Python $candidate)) { throw 'PythonExe is not a working Python 3.11 executable.' }
        return $candidate
    }

    $venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
    if (Test-Python $venvPython) { return $venvPython }
    foreach ($name in @('python3.11', 'python')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command -and (Test-Python $command.Source)) { return $command.Source }
    }
    throw 'No working Python 3.11 was found. Pass -PythonExe with its full path.'
}

if ([string]::IsNullOrWhiteSpace($Password)) {
    $Password = Read-PlainSecret 'Local PostgreSQL password'
}
if ([string]::IsNullOrWhiteSpace($FirmsMapKey)) {
    $FirmsMapKey = Read-PlainSecret 'NASA FIRMS MAP_KEY'
}

$psql = Resolve-PostgresTool 'psql'
$createdb = Resolve-PostgresTool 'createdb'
$dropdb = Resolve-PostgresTool 'dropdb'
$python = Resolve-Python311

# When a broken venv launcher is present but its packages are usable, an
# explicitly supplied system Python can still consume the repository venv.
$venvPackages = Join-Path $repoRoot '.venv\Lib\site-packages'
if ((Test-Path -LiteralPath $venvPackages) -and $python -notlike '*\.venv\Scripts\python.exe') {
    $env:PYTHONPATH = $venvPackages
}

& $python -c "import sqlalchemy, pandas, pyarrow, sklearn, xgboost, rasterio, psycopg" 2>$null
if ($LASTEXITCODE -ne 0) {
    if ($SkipDependencyInstall) {
        throw 'Required Python packages are missing and -SkipDependencyInstall was supplied.'
    }
    Write-Host 'Installing repository Python dependencies...'
    & $python -m pip install -r (Join-Path $repoRoot 'backend\requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
}

$previousPassword = $env:PGPASSWORD
$previousDatabaseUrl = $env:DATABASE_URL
$previousFirmsKey = $env:FIRMS_MAP_KEY
$env:PGPASSWORD = $Password
$encodedUser = [Uri]::EscapeDataString($Username)
$encodedPassword = [Uri]::EscapeDataString($Password)
$env:DATABASE_URL = "postgresql+psycopg://${encodedUser}:${encodedPassword}@${Server}:$Port/$Database"
$env:FIRMS_MAP_KEY = $FirmsMapKey
$env:FIRMS_PRIMARY_SOURCE = 'VIIRS_NOAA20_NRT'
$env:MODEL_STACK_VERSION = '2026-09-04-r1'
$env:PRITHVI_ENABLED = 'false'

Push-Location $repoRoot
try {
    $exists = & $psql --host=$Server --port=$Port --username=$Username `
        --dbname=postgres --tuples-only --no-align `
        --command="SELECT 1 FROM pg_database WHERE datname = '$Database'"
    if ($LASTEXITCODE -ne 0) { throw 'Could not connect to local PostgreSQL.' }
    $databaseExists = (($exists | Out-String).Trim() -eq '1')

    if ($databaseExists -and $Replace) {
        Write-Host "Replacing local database '$Database'..."
        & $dropdb --host=$Server --port=$Port --username=$Username --force --if-exists $Database
        if ($LASTEXITCODE -ne 0) { throw "Could not drop database '$Database'." }
        $databaseExists = $false
    } elseif ($databaseExists -and -not $Resume) {
        throw "Database '$Database' already exists. Use -Resume or explicitly use -Replace."
    }

    $needsBootstrap = -not $databaseExists
    if (-not $databaseExists) {
        & $createdb --host=$Server --port=$Port --username=$Username $Database
        if ($LASTEXITCODE -ne 0) { throw "Could not create database '$Database'." }

        Write-Host 'Creating ORM tables...'
        & $python backend/scripts/bootstrap_db.py --init-only
        if ($LASTEXITCODE -ne 0) { throw 'Initial schema creation failed.' }
    }

    Write-Host 'Applying the idempotent PostGIS runtime migration...'
    & $psql --host=$Server --port=$Port --username=$Username --dbname=$Database `
        --set=ON_ERROR_STOP=1 --file=backend/migrations/001_runtime_overhaul.sql
    if ($LASTEXITCODE -ne 0) { throw 'Runtime migration failed. Confirm PostGIS is installed.' }

    if ($needsBootstrap) {
        Write-Host 'Loading the frozen authoritative 2025 bootstrap...'
        & $python -u backend/scripts/bootstrap_db.py --clean
        if ($LASTEXITCODE -ne 0) { throw 'Authoritative 2025 bootstrap failed.' }
    }

    Write-Host "Running/resuming audited NOAA-20 backfill through $DataThrough..."
    & $python -u backend/scripts/backfill_firms_2026.py `
        --start-date 2026-01-01 --end-date $DataThrough --update-db
    if ($LASTEXITCODE -ne 0) { throw '2026 FIRMS backfill or final A/B/C refresh failed.' }

    Write-Host 'Verifying live-stack readiness...'
    & $python backend/scripts/verify_bootstrap_artifacts.py
    if ($LASTEXITCODE -ne 0) { throw 'Runtime readiness verification failed.' }

    Write-Host 'Writing the current alert-burden audit...'
    & $python backend/scripts/audit_alert_burden.py
    if ($LASTEXITCODE -ne 0) { throw 'Alert-burden audit failed.' }

    Write-Host "Local SIH26162 runtime is ready through $DataThrough."
} finally {
    Pop-Location
    $env:PGPASSWORD = $previousPassword
    $env:DATABASE_URL = $previousDatabaseUrl
    $env:FIRMS_MAP_KEY = $previousFirmsKey
    $env:PYTHONPATH = $previousPythonPath
}
