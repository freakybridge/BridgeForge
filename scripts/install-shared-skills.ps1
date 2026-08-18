#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(DontShow = $true)]
    [switch]$TestNonWindows
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$CanonicalRemote = "https://github.com/freakybridge/BridgeForgeCodex.git"
$CanonicalBranch = "main"

function Assert-Windows {
    if ($TestNonWindows -or [Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw "bridgeforge-codex shared-skill distribution supports Windows only."
    }
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$WorkingDirectory
    )
    $oldLocation = Get-Location
    try {
        if ($WorkingDirectory) {
            Set-Location -LiteralPath $WorkingDirectory
        }
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $output = & git @Arguments 2>&1
            $exitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousPreference
        }
        if ($exitCode -ne 0) {
            throw "git $($Arguments -join ' ') failed: $($output -join [Environment]::NewLine)"
        }
        return @($output)
    }
    finally {
        Set-Location -LiteralPath $oldLocation
    }
}

function Get-NormalizedRemote {
    param([Parameter(Mandatory = $true)][string]$Remote)
    $value = $Remote.Trim().TrimEnd("/")
    if ($value.EndsWith(".git", [StringComparison]::OrdinalIgnoreCase)) {
        $value = $value.Substring(0, $value.Length - 4)
    }
    return $value.ToLowerInvariant()
}

function Assert-CanonicalRepositoryIdentity {
    param([Parameter(Mandatory = $true)][string]$Root)
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "Repository path does not exist: $Root"
    }
    $remote = ((Invoke-Git -WorkingDirectory $Root -Arguments @("config", "--get", "remote.origin.url")) -join "").Trim()
    if ((Get-NormalizedRemote $remote) -ne (Get-NormalizedRemote $CanonicalRemote)) {
        throw "Repository origin is not the canonical bridgeforge-codex remote."
    }
    Invoke-Git -WorkingDirectory $Root -Arguments @(
        "fetch",
        "--no-tags",
        "--prune",
        "origin",
        "+refs/heads/main:refs/remotes/origin/main"
    ) | Out-Null
    $branch = ((Invoke-Git -WorkingDirectory $Root -Arguments @("symbolic-ref", "--short", "HEAD")) -join "").Trim()
    if ($branch -ne $CanonicalBranch) {
        throw "Repository does not have main checked out."
    }
    $commit = ((Invoke-Git -WorkingDirectory $Root -Arguments @("rev-parse", "HEAD")) -join "").Trim().ToLowerInvariant()
    if ($commit -notmatch "^[0-9a-fA-F]{40}$") {
        throw "Repository HEAD is not a full commit SHA."
    }
    $remoteCommit = ((
        Invoke-Git -WorkingDirectory $Root -Arguments @("rev-parse", "refs/remotes/origin/main")
    ) -join "").Trim().ToLowerInvariant()
    if ($remoteCommit -notmatch "^[0-9a-f]{40}$" -or $commit -ne $remoteCommit) {
        throw "Repository HEAD does not match the fetched canonical origin/main."
    }
    if (Test-Path -LiteralPath (Join-Path $Root ".gitmodules")) {
        throw "Submodules are not allowed in the shared-skill source."
    }
}

function Remove-TemporaryClone {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd("\") + "\"
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a clone outside the system temporary directory: $resolved"
    }
    $item = Get-Item -LiteralPath $resolved -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to recursively remove a reparse point: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

function Invoke-Main {
    # This must remain the first operation: non-Windows hosts get zero filesystem writes.
    Assert-Windows
    if ([string]::IsNullOrWhiteSpace([string]$env:USERPROFILE) -or
        -not (Test-Path -LiteralPath $env:USERPROFILE -PathType Container)) {
        throw "USERPROFILE is not a valid existing directory."
    }

    $cloneRoot = Join-Path ([IO.Path]::GetTempPath()) "bridgeforge-codex-bootstrap-$([Guid]::NewGuid().ToString('N'))"
    try {
        Invoke-Git -Arguments @(
            "-c", "core.autocrlf=false",
            "clone",
            "--branch", $CanonicalBranch,
            "--single-branch",
            "--depth", "1",
            "--no-recurse-submodules",
            $CanonicalRemote,
            $cloneRoot
        ) | Out-Null
        Assert-CanonicalRepositoryIdentity -Root $cloneRoot
        $updater = Join-Path $cloneRoot "scripts\bridgeforge_codex_shared_update.ps1"
        if (-not (Test-Path -LiteralPath $updater -PathType Leaf)) {
            throw "Canonical clone is missing the shared-skill updater."
        }
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $updater -SourceRepositoryRoot $cloneRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Shared-skill updater failed with exit code $LASTEXITCODE."
        }
        Write-Host 'bridgeforge-codex shared-skill installation completed. Run $bridgeforge-codex in Codex.'
    }
    finally {
        if (Test-Path -LiteralPath $cloneRoot) {
            Remove-TemporaryClone -Path $cloneRoot
        }
    }
}

try {
    Invoke-Main
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
