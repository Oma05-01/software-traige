
$ErrorActionPreference = "Stop"

$RepositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..\..")
)

$ExportScript = Join-Path $PSScriptRoot "export-postgres-backups.ps1"

$LogDirectory = Join-Path $RepositoryRoot "backups\logs"

New-Item -ItemType Directory -Force -Path $LogDirectory |
    Out-Null

# Retain export logs for 30 days.
Get-ChildItem -LiteralPath $LogDirectory -Filter "export-*.log" -File |
    Where-Object {
        $_.LastWriteTime -lt (Get-Date).AddDays(-30)
    } |
    Remove-Item -Force

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogFile = Join-Path $LogDirectory "export-$Timestamp.log"

$ExitCode = 0

Start-Transcript -Path $LogFile | Out-Null

try {
    Write-Host "Starting scheduled PostgreSQL backup export."
    Write-Host "Repository: $RepositoryRoot"
    Write-Host "Started: $(Get-Date)"

    & $ExportScript

    Write-Host "Backup export completed successfully."
}
catch {
    Write-Host "BACKUP EXPORT FAILED:"
    Write-Host $_.Exception.Message
    $ExitCode = 1
}
finally {
    Write-Host "Finished: $(Get-Date)"
    Stop-Transcript | Out-Null
}

exit $ExitCode