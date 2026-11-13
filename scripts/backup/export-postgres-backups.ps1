
param(
    [string]$Namespace = "software-triage",
    [string]$BackupDirectory = (Join-Path $PSScriptRoot "..\..\backups")
)

$ErrorActionPreference = "Stop"

$BackupDirectory = [System.IO.Path]::GetFullPath($BackupDirectory)

$RepositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..\..")
)

$StagingDirectory = Join-Path $RepositoryRoot "backups\.staging"

New-Item -ItemType Directory -Force -Path $BackupDirectory |
    Out-Null

New-Item -ItemType Directory -Force -Path $StagingDirectory |
    Out-Null

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw "kubectl was not found in PATH."
}

Write-Host "`n=== POSTGRESQL BACKUP EXPORT ==="
Write-Host "Namespace: $Namespace"
Write-Host "Destination: $BackupDirectory"


# Wait for the exporter Deployment to become available.
Write-Host "`nChecking Kubernetes backup exporter..."

$deploymentWaitOutput = & kubectl wait `
    --for=condition=Available `
    deployment/postgres-backup-exporter `
    -n $Namespace `
    --timeout=120s 2>&1

$deploymentWaitExitCode = $LASTEXITCODE

if ($deploymentWaitExitCode -ne 0) {
    $details = ($deploymentWaitOutput | Out-String).Trim()

    throw "Backup exporter is unavailable. Ensure Docker Desktop and Kubernetes are running. Details: $details"
}

# Retrieve the exporter pod name safely.
$podOutput = & kubectl get pods `
    -n $Namespace `
    -l app=postgres-backup-exporter `
    -o jsonpath='{.items[0].metadata.name}' 2>&1

$podExitCode = $LASTEXITCODE
$exporterPod = ($podOutput | Out-String).Trim()

if ($podExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($exporterPod)) {
    $details = ($podOutput | Out-String).Trim()

    throw "Could not locate a ready backup exporter pod. Details: $details"
}

# Confirm the selected pod is ready.
$podWaitOutput = & kubectl wait `
    --for=condition=Ready `
    "pod/$exporterPod" `
    -n $Namespace `
    --timeout=60s 2>&1

$podWaitExitCode = $LASTEXITCODE

if ($podWaitExitCode -ne 0) {
    $details = ($podWaitOutput | Out-String).Trim()

    throw "Backup exporter pod is not ready. Details: $details"
}


# List completed backup archives.
$remoteOutput = @(
    & kubectl exec `
        -n $Namespace `
        $exporterPod `
        -- sh -c "find /backups -maxdepth 1 -type f -name 'software-triage-*.dump' -print"
)

if ($LASTEXITCODE -ne 0) {
    throw "Could not list backup files on the PVC."
}

$remoteFiles = @(
    $remoteOutput |
        ForEach-Object { "$_".Trim() } |
        Where-Object {
            $_ -match '^/backups/software-triage-\d{8}T\d{6}Z\.dump$'
        }
)

if ($remoteFiles.Count -eq 0) {
    throw "No completed PostgreSQL backup archives were found."
}

$copied = 0
$skipped = 0

foreach ($remoteFile in $remoteFiles) {

    $fileName = Split-Path $remoteFile -Leaf
    $localFile = Join-Path $BackupDirectory $fileName

    Write-Host "`n--- Processing $fileName ---"

    # Get the source checksum.
    $remoteHashOutput = @(
        & kubectl exec `
            -n $Namespace `
            $exporterPod `
            -- sha256sum $remoteFile
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Could not calculate source checksum for $fileName."
    }

    $remoteHash = ($remoteHashOutput[0] -split '\s+')[0].ToUpperInvariant()

    if ($remoteHash -notmatch '^[A-F0-9]{64}$') {
        throw "Invalid source checksum for $fileName."
    }

    # Verify the source archive without printing its contents.
    & kubectl exec `
        -n $Namespace `
        $exporterPod `
        -- sh -c "pg_restore --list '$remoteFile' > /dev/null"

    if ($LASTEXITCODE -ne 0) {
        throw "Source archive validation failed for $fileName."
    }

    # Never overwrite an existing local archive.
    if (Test-Path -LiteralPath $localFile) {

        $existingHash = (
            Get-FileHash `
                -LiteralPath $localFile `
                -Algorithm SHA256
        ).Hash

        if ($existingHash -ne $remoteHash) {
            throw "Checksum mismatch for existing local file: $fileName."
        }

        Write-Host "Already exists and verified. Skipping."
        $skipped++
        continue
    }

    # Use a relative destination for kubectl cp.
    $stagingFile = Join-Path $StagingDirectory $fileName
    $stagingRelativePath = ".\backups\.staging\$fileName"

    if (Test-Path -LiteralPath $stagingFile) {
        throw "A staging file already exists: $stagingFile"
    }

    Push-Location $RepositoryRoot

    try {
        & kubectl cp `
            -n $Namespace `
            "${exporterPod}:$remoteFile" `
            $stagingRelativePath

        $copyExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($copyExitCode -ne 0) {
        throw "Failed to copy $fileName."
    }

    if (!(Test-Path -LiteralPath $stagingFile)) {
        throw "Copied staging file was not found."
    }

    # Verify the staged file before moving it.
    $stagingHash = (
        Get-FileHash `
            -LiteralPath $stagingFile `
            -Algorithm SHA256
    ).Hash

    if ($stagingHash -ne $remoteHash) {
        Remove-Item -LiteralPath $stagingFile -Force
        throw "Checksum mismatch for $fileName. Invalid staging file removed."
    }

    # Move only the verified file to the final destination.
    Move-Item `
        -LiteralPath $stagingFile `
        -Destination $localFile

    Write-Host "Copied and verified successfully."
    Write-Host "SHA256: $stagingHash"

    $copied++
}

Write-Host "`n=== EXPORT SUMMARY ==="
Write-Host "New backups copied: $copied"
Write-Host "Existing backups verified: $skipped"
Write-Host "Total archives processed: $($remoteFiles.Count)"

Write-Host "`nBackup synchronisation completed successfully."
