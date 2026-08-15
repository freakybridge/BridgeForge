#requires -Version 5.1
[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("refresh")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundleRoot = Split-Path -Parent $scriptRoot
$sharedUpdater = Join-Path $scriptRoot "bridgeforge_shared_update.ps1"

function Assert-BundleFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    $bundleFull = [IO.Path]::GetFullPath($bundleRoot).TrimEnd("\", "/")
    $pathFull = [IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($bundleFull + "\", [StringComparison]::OrdinalIgnoreCase) -or
        -not (Test-Path -LiteralPath $pathFull -PathType Leaf)) {
        throw "Required managed bundle file is missing or escapes the bundle: $Path"
    }
}

Assert-BundleFile -Path $sharedUpdater

switch ($Action) {
    "refresh" {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $sharedUpdater
        exit $LASTEXITCODE
    }
}
