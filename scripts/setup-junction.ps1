#requires -Version 5.0
<#
.SYNOPSIS
    Setup memory junction: ~/.claude/projects/<hash>/memory/ -> <project>/.claude/memory/

.DESCRIPTION
    Creates an NTFS junction so Claude Code's per-project memory directory
    (under user home) transparently redirects to a directory inside the
    project (under git management). This makes memory clone-recoverable
    across machines.

.PARAMETER ProjectPath
    Absolute path to the project root (the directory containing .claude/).

.EXAMPLE
    .\setup-junction.ps1 -ProjectPath "D:\Quant\MyProject"

.NOTES
    Junction creation does NOT require admin on NTFS volumes (unlike symlinks).
    Requires PowerShell 5.0+. Tested on Windows 10/11.
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectPath
)

$ErrorActionPreference = 'Stop'

# 1. Validate project path
if (-not (Test-Path $ProjectPath -PathType Container)) {
    Write-Error "Project path not found or not a directory: $ProjectPath"
    exit 1
}

$ProjectAbs = (Resolve-Path $ProjectPath).Path
$ProjectMemoryDir = Join-Path $ProjectAbs ".claude\memory"

# 2. Ensure project-side .claude/memory/ exists
if (-not (Test-Path $ProjectMemoryDir -PathType Container)) {
    Write-Host "Creating project memory dir: $ProjectMemoryDir"
    New-Item -ItemType Directory -Path $ProjectMemoryDir -Force | Out-Null
}

# 3. Compute project hash (Claude Code uses dash-separated path with drive prefix)
#    Example: D:\Quant\MyProject -> d--Quant-MyProject
$drive = Split-Path -Qualifier $ProjectAbs   # "D:"
$rest = Split-Path -NoQualifier $ProjectAbs  # "\Quant\MyProject"
$driveLetter = $drive.TrimEnd(':').ToLower()
$pathSegment = $rest.TrimStart('\').Replace('\', '-')
$projectHash = "$driveLetter--$pathSegment"

$systemMemoryParent = Join-Path $env:USERPROFILE ".claude\projects\$projectHash"
$systemMemoryDir = Join-Path $systemMemoryParent "memory"

Write-Host "Project hash:        $projectHash"
Write-Host "System memory path:  $systemMemoryDir"
Write-Host "Project memory path: $ProjectMemoryDir"

# 4. Ensure parent dir exists
if (-not (Test-Path $systemMemoryParent -PathType Container)) {
    New-Item -ItemType Directory -Path $systemMemoryParent -Force | Out-Null
}

# 5. Handle existing system memory dir
if (Test-Path $systemMemoryDir) {
    $item = Get-Item $systemMemoryDir -Force
    if ($item.LinkType -eq 'Junction' -or $item.LinkType -eq 'SymbolicLink') {
        $existingTarget = $item.Target
        if ($existingTarget -eq $ProjectMemoryDir) {
            Write-Host "Junction already exists and points to the right target. Skipping." -ForegroundColor Green
            exit 0
        } else {
            Write-Warning "Junction exists but points to: $existingTarget"
            Write-Warning "Will replace with target: $ProjectMemoryDir"
            $resp = Read-Host "Continue? [y/N]"
            if ($resp -ne 'y') { exit 1 }
            Remove-Item $systemMemoryDir -Force
        }
    } elseif ($item.PSIsContainer) {
        $entries = Get-ChildItem $systemMemoryDir -Force
        if ($entries.Count -gt 0) {
            Write-Warning "System memory dir is non-empty (regular dir): $systemMemoryDir"
            Write-Warning "Manually backup its content into $ProjectMemoryDir, then delete the system dir, then re-run this script."
            exit 1
        } else {
            Write-Host "System memory dir is empty. Removing and creating junction."
            Remove-Item $systemMemoryDir -Force
        }
    } else {
        Write-Error "Unexpected file at system memory path: $systemMemoryDir"
        exit 1
    }
}

# 6. Create junction
Write-Host "Creating junction..."
New-Item -ItemType Junction -Path $systemMemoryDir -Target $ProjectMemoryDir | Out-Null

# 7. Verify
$verify = Get-Item $systemMemoryDir -Force
if ($verify.LinkType -eq 'Junction' -and $verify.Target -eq $ProjectMemoryDir) {
    Write-Host "Junction created successfully:" -ForegroundColor Green
    Write-Host "  $systemMemoryDir  ->  $ProjectMemoryDir" -ForegroundColor Green
} else {
    Write-Error "Junction verification failed."
    exit 1
}
