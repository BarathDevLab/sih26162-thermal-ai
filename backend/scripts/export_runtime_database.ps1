[CmdletBinding()]
param(
    [string]$Server = 'localhost',
    [int]$Port = 5432,
    [string]$Database = 'sih26162',
    [string]$Username = 'postgres',
    [string]$Password = $env:POSTGRES_PASSWORD,
    [string]$OutputPath,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

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
if ([string]::IsNullOrWhiteSpace($Password)) {
    $Password = Read-PlainSecret 'Local PostgreSQL password'
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $OutputPath = Join-Path $repoRoot "data\database_snapshots\sih26162_runtime_$stamp.dump"
} elseif (-not [IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $repoRoot $OutputPath
}

$target = [IO.Path]::GetFullPath($OutputPath)
if ((Test-Path -LiteralPath $target) -and -not $Force) {
    throw "Snapshot already exists: $target. Use -Force to replace this exact file."
}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null

$pgDump = Resolve-PostgresTool 'pg_dump'
$psql = Resolve-PostgresTool 'psql'
$previousPassword = $env:PGPASSWORD
$env:PGPASSWORD = $Password

try {
    Write-Host "Exporting '$Database' to a compressed, consistent PostgreSQL snapshot..."
    & $pgDump `
        --host=$Server `
        --port=$Port `
        --username=$Username `
        --dbname=$Database `
        --format=custom `
        --compress=9 `
        --no-owner `
        --no-acl `
        --exclude-schema=backup_runtime_* `
        --lock-wait-timeout=60000 `
        --file=$target
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE." }

    $databaseBytes = (& $psql --host=$Server --port=$Port --username=$Username `
        --dbname=$Database --tuples-only --no-align `
        --command='SELECT pg_database_size(current_database())').Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not read database size after export.' }
    $serverVersion = (& $psql --host=$Server --port=$Port --username=$Username `
        --dbname=$Database --tuples-only --no-align `
        --command='SHOW server_version').Trim()
    $siteCount = (& $psql --host=$Server --port=$Port --username=$Username `
        --dbname=$Database --tuples-only --no-align `
        --command='SELECT count(*) FROM source_sites').Trim()
    $detectionCount = (& $psql --host=$Server --port=$Port --username=$Username `
        --dbname=$Database --tuples-only --no-align `
        --command='SELECT count(*) FROM firms_detections').Trim()
    $latestDate = (& $psql --host=$Server --port=$Port --username=$Username `
        --dbname=$Database --tuples-only --no-align `
        --command='SELECT max(acq_date) FROM site_daily_activity').Trim()

    $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    $hashPath = "$target.sha256"
    "$hash  $([IO.Path]::GetFileName($target))" | Set-Content -LiteralPath $hashPath -Encoding ascii

    $gitCommit = (& git -C $repoRoot rev-parse HEAD 2>$null | Out-String).Trim()
    $metadata = [ordered]@{
        schema_version = '1.0'
        created_at_utc = [datetime]::UtcNow.ToString('o')
        database = $Database
        server_version = $serverVersion
        database_bytes = [int64]$databaseBytes
        dump_bytes = (Get-Item -LiteralPath $target).Length
        sha256 = $hash
        repository_commit = $gitCommit
        source_sites = [int64]$siteCount
        firms_detections = [int64]$detectionCount
        data_through = $latestDate
        excluded_schemas = @('backup_runtime_*')
        restore_tool = 'backend/scripts/restore_runtime_database.ps1'
    }
    $metadataPath = "$target.json"
    $metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8

    Write-Host ''
    Write-Host 'Snapshot ready to share:'
    Write-Host "  Dump:     $target"
    Write-Host "  Checksum: $hashPath"
    Write-Host "  Metadata: $metadataPath"
    Write-Host "  Size:     $([math]::Round($metadata.dump_bytes / 1MB, 1)) MB"
} catch {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Force
    }
    throw
} finally {
    $env:PGPASSWORD = $previousPassword
}
