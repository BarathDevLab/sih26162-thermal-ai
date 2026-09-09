[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DumpPath,
    [string]$Server = 'localhost',
    [int]$Port = 5432,
    [string]$Database = 'sih26162',
    [string]$Username = 'postgres',
    [string]$Password = $env:POSTGRES_PASSWORD,
    [int]$Jobs = 4,
    [switch]$Replace,
    [switch]$SkipChecksum
)

$ErrorActionPreference = 'Stop'

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

if ($Database -notmatch '^[A-Za-z][A-Za-z0-9_]{0,62}$') {
    throw 'Database must be a simple PostgreSQL identifier.'
}
if ($Jobs -lt 1) { throw 'Jobs must be at least 1.' }
$snapshot = (Resolve-Path -LiteralPath $DumpPath).Path
if ([string]::IsNullOrWhiteSpace($Password)) {
    $Password = Read-PlainSecret 'Local PostgreSQL password'
}

if (-not $SkipChecksum) {
    $hashPath = "$snapshot.sha256"
    if (-not (Test-Path -LiteralPath $hashPath)) {
        throw "Checksum sidecar is missing: $hashPath. Copy it beside the dump or use -SkipChecksum explicitly."
    }
    $expected = ((Get-Content -LiteralPath $hashPath -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    $actual = (Get-FileHash -LiteralPath $snapshot -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw 'Snapshot SHA-256 checksum mismatch.' }
    Write-Host 'Snapshot checksum verified.'
}

$pgRestore = Resolve-PostgresTool 'pg_restore'
$psql = Resolve-PostgresTool 'psql'
$createdb = Resolve-PostgresTool 'createdb'
$dropdb = Resolve-PostgresTool 'dropdb'
$previousPassword = $env:PGPASSWORD
$env:PGPASSWORD = $Password

try {
    $exists = & $psql --host=$Server --port=$Port --username=$Username `
        --dbname=postgres --tuples-only --no-align `
        --command="SELECT 1 FROM pg_database WHERE datname = '$Database'"
    if ($LASTEXITCODE -ne 0) { throw 'Could not connect to PostgreSQL.' }
    $databaseExists = (($exists | Out-String).Trim() -eq '1')

    if ($databaseExists -and -not $Replace) {
        throw "Database '$Database' already exists. Use -Replace to explicitly replace it."
    }
    if ($databaseExists) {
        Write-Host "Replacing database '$Database'..."
        & $dropdb --host=$Server --port=$Port --username=$Username --force $Database
        if ($LASTEXITCODE -ne 0) { throw "Could not drop database '$Database'." }
    }

    & $createdb --host=$Server --port=$Port --username=$Username $Database
    if ($LASTEXITCODE -ne 0) { throw "Could not create database '$Database'." }

    Write-Host "Restoring with $Jobs parallel workers..."
    & $pgRestore `
        --host=$Server `
        --port=$Port `
        --username=$Username `
        --dbname=$Database `
        --jobs=$Jobs `
        --no-owner `
        --no-acl `
        --exit-on-error `
        $snapshot
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit code $LASTEXITCODE." }

    $verification = & $psql --host=$Server --port=$Port --username=$Username `
        --dbname=$Database --tuples-only --no-align --field-separator='|' `
        --command="SELECT (SELECT count(*) FROM source_sites), (SELECT count(*) FROM firms_detections), (SELECT max(acq_date) FROM site_daily_activity), EXISTS(SELECT 1 FROM pg_extension WHERE extname='postgis')"
    if ($LASTEXITCODE -ne 0) { throw 'Restored database verification failed.' }
    $values = (($verification | Out-String).Trim() -split '\|')
    if ($values.Count -ne 4 -or $values[3] -ne 't') {
        throw 'Restored database is missing expected runtime data or PostGIS.'
    }

    Write-Host ''
    Write-Host 'Restore complete.'
    Write-Host "  Source sites:     $($values[0])"
    Write-Host "  FIRMS detections: $($values[1])"
    Write-Host "  Data through:     $($values[2])"
    Write-Host '  PostGIS:          enabled'
    Write-Host "Set DATABASE_URL=postgresql+psycopg://${Username}:<password>@${Server}:$Port/$Database"
} finally {
    $env:PGPASSWORD = $previousPassword
}
