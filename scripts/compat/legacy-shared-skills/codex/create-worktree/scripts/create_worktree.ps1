#requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$worktree_name,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$branch_name,

    [string]$base_branch = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Stop-CreateWorktree {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [int]$ExitCode = 2
    )

    [Console]::Error.WriteLine("[create-worktree] $Message")
    exit $ExitCode
}

function Invoke-GitCommand {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $commandOutput = @(& git @Arguments 2>&1)
        $commandExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
    return [PSCustomObject]@{
        ExitCode = $commandExitCode
        Output = $commandOutput
        Text = [string]($commandOutput -join [Environment]::NewLine)
    }
}

function Assert-GitSuccess {
    param(
        [Parameter(Mandatory = $true)]$Result,
        [Parameter(Mandatory = $true)][string]$Context,
        [int]$ExitCode = 2
    )

    if ($Result.ExitCode -ne 0) {
        $detail = $Result.Text.Trim()
        if (-not $detail) {
            $detail = "git exit $($Result.ExitCode)"
        }
        Stop-CreateWorktree "${Context}: $detail" $ExitCode
    }
}

function Read-WorktreeRoot {
    param([Parameter(Mandatory = $true)][string]$ConfigPath)

    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        Stop-CreateWorktree "Missing Codex config file: $ConfigPath"
    }

    $inDesktop = $false
    $desktopSeen = $false
    $rootSeen = $false
    $rootValue = $null

    foreach ($line in [IO.File]::ReadAllLines($ConfigPath, [Text.Encoding]::UTF8)) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        if ($trimmed -match '^\[([^\]]+)\]\s*(?:#.*)?$') {
            $section = $Matches[1].Trim()
            $inDesktop = $section -ceq "desktop"
            if ($inDesktop) {
                if ($desktopSeen) {
                    Stop-CreateWorktree "config.toml contains a duplicate [desktop] table"
                }
                $desktopSeen = $true
            }
            continue
        }

        if (-not $inDesktop) {
            continue
        }

        if ($trimmed -match '^git-worktree-root\s*=\s*("(?:\\.|[^"\\])*")\s*(?:#.*)?$') {
            if ($rootSeen) {
                Stop-CreateWorktree "config.toml contains duplicate desktop.git-worktree-root keys"
            }
            try {
                $rootValue = $Matches[1] | ConvertFrom-Json
            } catch {
                Stop-CreateWorktree "desktop.git-worktree-root is not a valid quoted TOML string"
            }
            $rootSeen = $true
            continue
        }

        if ($trimmed -match "^git-worktree-root\s*=\s*'([^']*)'\s*(?:#.*)?$") {
            if ($rootSeen) {
                Stop-CreateWorktree "config.toml contains duplicate desktop.git-worktree-root keys"
            }
            $rootValue = $Matches[1]
            $rootSeen = $true
            continue
        }

        if ($trimmed -match '^git-worktree-root\s*=') {
            Stop-CreateWorktree "desktop.git-worktree-root must be a quoted, non-empty absolute path"
        }
    }

    if (-not $desktopSeen -or -not $rootSeen -or [string]::IsNullOrWhiteSpace([string]$rootValue)) {
        Stop-CreateWorktree "config.toml is missing a non-empty desktop.git-worktree-root"
    }

    $configuredRoot = [string]$rootValue
    if (-not [IO.Path]::IsPathRooted($configuredRoot)) {
        Stop-CreateWorktree "desktop.git-worktree-root must be absolute: $configuredRoot"
    }
    if (-not (Test-Path -LiteralPath $configuredRoot -PathType Container)) {
        Stop-CreateWorktree "desktop.git-worktree-root does not exist: $configuredRoot"
    }

    try {
        return (Get-Item -LiteralPath $configuredRoot -Force).FullName
    } catch {
        Stop-CreateWorktree "Cannot resolve desktop.git-worktree-root: $($_.Exception.Message)"
    }
}

function Assert-WorktreeName {
    param([Parameter(Mandatory = $true)][string]$Name)

    if ($Name -ne $Name.Trim() -or $Name -in @(".", "..")) {
        Stop-CreateWorktree "worktree_name must be one valid directory name"
    }
    if ([IO.Path]::IsPathRooted($Name) -or $Name.IndexOfAny(@([char]'\', [char]'/', [char]':')) -ge 0) {
        Stop-CreateWorktree "worktree_name must not contain a path or drive: $Name"
    }
    if ($Name.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0 -or $Name.EndsWith(".") -or $Name.EndsWith(" ")) {
        Stop-CreateWorktree "worktree_name contains invalid Windows filename characters: $Name"
    }
    if ($Name -match '^(?i:CON|PRN|AUX|NUL|COM(?:[1-9]|\u00B9|\u00B2|\u00B3)|LPT(?:[1-9]|\u00B9|\u00B2|\u00B3))(?:\..*)?$') {
        Stop-CreateWorktree "worktree_name is a reserved Windows name: $Name"
    }
}

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [IO.Path]::GetFullPath($Path).TrimEnd([char]'\', [char]'/')
}

function Assert-NoReparsePointInExistingAncestors {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label
    )

    try {
        $currentPath = [IO.Path]::GetFullPath($Path)
        while ($currentPath) {
            if (Test-Path -LiteralPath $currentPath) {
                $item = Get-Item -LiteralPath $currentPath -Force
                if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    Stop-CreateWorktree "$Label passes through a reparse point: $currentPath"
                }
            }

            $parent = [IO.Directory]::GetParent($currentPath)
            if ($null -eq $parent) {
                break
            }
            $parentPath = $parent.FullName
            if ([string]::Equals($parentPath, $currentPath, [StringComparison]::OrdinalIgnoreCase)) {
                break
            }
            $currentPath = $parentPath
        }
    } catch {
        Stop-CreateWorktree "Cannot inspect $Label ancestors: $($_.Exception.Message)"
    }
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        Stop-CreateWorktree "This skill only supports Windows"
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Stop-CreateWorktree "git executable was not found"
    }
    if ([string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        Stop-CreateWorktree "USERPROFILE is empty; cannot locate ~/.codex/config.toml"
    }

    Assert-WorktreeName $worktree_name

    if ($branch_name -ne $branch_name.Trim() -or [string]::IsNullOrWhiteSpace($branch_name)) {
        Stop-CreateWorktree "branch_name is empty or has surrounding whitespace"
    }
    $fullBranch = if ($branch_name.StartsWith("codex/", [StringComparison]::Ordinal)) {
        $branch_name
    } else {
        "codex/$branch_name"
    }

    $targetBranchFormat = Invoke-GitCommand @("check-ref-format", "--branch", $fullBranch)
    if ($targetBranchFormat.ExitCode -ne 0) {
        Stop-CreateWorktree "Invalid target branch name: $fullBranch"
    }
    $repoResult = Invoke-GitCommand @("-C", (Get-Location).Path, "rev-parse", "--show-toplevel")
    Assert-GitSuccess $repoResult "Current directory is not inside a valid Git repository"
    $repoRoot = $repoResult.Text.Trim()
    if (-not $repoRoot) {
        Stop-CreateWorktree "Git did not return a repository root"
    }
    $repoRoot = Get-NormalizedPath $repoRoot
    Assert-NoReparsePointInExistingAncestors $repoRoot "Source repository root"

    $statusBefore = Invoke-GitCommand @("-C", $repoRoot, "status", "--porcelain=v1", "--untracked-files=all")
    Assert-GitSuccess $statusBefore "Cannot inspect the source repository status"
    if ($statusBefore.Text) {
        Stop-CreateWorktree "Source repository has modified, staged, or untracked files; handle them and retry"
    }

    if ($base_branch -eq "") {
        $mainExists = Invoke-GitCommand @("-C", $repoRoot, "show-ref", "--verify", "--quiet", "refs/heads/main")
        if ($mainExists.ExitCode -eq 0) {
            $base_branch = "main"
        } elseif ($mainExists.ExitCode -ne 1) {
            Stop-CreateWorktree "Cannot verify whether local main exists: $($mainExists.Text.Trim())"
        } else {
            $masterExists = Invoke-GitCommand @("-C", $repoRoot, "show-ref", "--verify", "--quiet", "refs/heads/master")
            if ($masterExists.ExitCode -eq 0) {
                $base_branch = "master"
            } elseif ($masterExists.ExitCode -ne 1) {
                Stop-CreateWorktree "Cannot verify whether local master exists: $($masterExists.Text.Trim())"
            } else {
                Stop-CreateWorktree "No local main or master branch exists; provide the optional third base branch argument"
            }
        }
    } elseif ([string]::IsNullOrWhiteSpace($base_branch) -or $base_branch -ne $base_branch.Trim()) {
        Stop-CreateWorktree "base_branch is empty or has surrounding whitespace"
    }

    $baseBranchFormat = Invoke-GitCommand @("check-ref-format", "--branch", $base_branch)
    if ($baseBranchFormat.ExitCode -ne 0) {
        Stop-CreateWorktree "Invalid base branch name: $base_branch"
    }

    $baseExists = Invoke-GitCommand @("-C", $repoRoot, "show-ref", "--verify", "--quiet", "refs/heads/$base_branch")
    if ($baseExists.ExitCode -ne 0) {
        Stop-CreateWorktree "Local base branch does not exist: $base_branch"
    }
    $targetExists = Invoke-GitCommand @("-C", $repoRoot, "show-ref", "--verify", "--quiet", "refs/heads/$fullBranch")
    if ($targetExists.ExitCode -eq 0) {
        Stop-CreateWorktree "Target branch already exists: $fullBranch"
    }
    if ($targetExists.ExitCode -ne 1) {
        Stop-CreateWorktree "Cannot verify whether the target branch exists: $($targetExists.Text.Trim())"
    }

    $baseCommitResult = Invoke-GitCommand @("-C", $repoRoot, "rev-parse", "refs/heads/$base_branch")
    Assert-GitSuccess $baseCommitResult "Cannot resolve the local base branch commit"
    $baseCommit = $baseCommitResult.Text.Trim()

    $sourceHeadBefore = Invoke-GitCommand @("-C", $repoRoot, "rev-parse", "HEAD")
    Assert-GitSuccess $sourceHeadBefore "Cannot read the source repository HEAD"
    $sourceBranchBefore = Invoke-GitCommand @("-C", $repoRoot, "symbolic-ref", "--quiet", "--short", "HEAD")

    $configPath = Join-Path (Join-Path $env:USERPROFILE ".codex") "config.toml"
    $worktreeRoot = Read-WorktreeRoot $configPath
    Assert-NoReparsePointInExistingAncestors $worktreeRoot "desktop.git-worktree-root"
    $targetPath = Get-NormalizedPath (Join-Path $worktreeRoot $worktree_name)
    $targetParent = Get-NormalizedPath ([IO.Path]::GetDirectoryName($targetPath))
    $normalizedRoot = Get-NormalizedPath $worktreeRoot
    if (-not [string]::Equals($targetParent, $normalizedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Stop-CreateWorktree "Target path is not a direct child of desktop.git-worktree-root"
    }
    $repoPrefix = $repoRoot.TrimEnd([char]'\', [char]'/') + [IO.Path]::DirectorySeparatorChar
    if (
        [string]::Equals($targetPath, $repoRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $targetPath.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)
    ) {
        Stop-CreateWorktree "Target path must be outside the source repository: $targetPath"
    }
    if (Test-Path -LiteralPath $targetPath) {
        Stop-CreateWorktree "Target path already exists: $targetPath"
    }

    $existingWorktrees = Invoke-GitCommand @("-C", $repoRoot, "-c", "core.quotePath=false", "worktree", "list", "--porcelain")
    Assert-GitSuccess $existingWorktrees "Cannot inspect existing worktree registrations"
    foreach ($recordLine in $existingWorktrees.Output) {
        $recordText = [string]$recordLine
        if ($recordText.StartsWith("worktree ")) {
            $listedPath = Get-NormalizedPath $recordText.Substring(9)
            if ([string]::Equals($listedPath, $targetPath, [StringComparison]::OrdinalIgnoreCase)) {
                Stop-CreateWorktree "Target path is already registered as a Git worktree: $targetPath"
            }
        }
    }

    $created = Invoke-GitCommand @("-C", $repoRoot, "worktree", "add", "-b", $fullBranch, $targetPath, $base_branch)
    if ($created.ExitCode -ne 0) {
        Stop-CreateWorktree "git worktree add -b failed; no automatic cleanup was attempted. $($created.Text.Trim())"
    }

    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        Stop-CreateWorktree "Post-create verification failed: target directory is missing; Git results were preserved" 4
    }

    $targetBranchResult = Invoke-GitCommand @("-C", $targetPath, "symbolic-ref", "--quiet", "--short", "HEAD")
    if ($targetBranchResult.ExitCode -ne 0 -or $targetBranchResult.Text.Trim() -cne $fullBranch) {
        Stop-CreateWorktree "Post-create verification failed: target branch is not $fullBranch; Git results were preserved" 4
    }
    $targetHeadResult = Invoke-GitCommand @("-C", $targetPath, "rev-parse", "HEAD")
    if ($targetHeadResult.ExitCode -ne 0 -or $targetHeadResult.Text.Trim() -cne $baseCommit) {
        Stop-CreateWorktree "Post-create verification failed: target HEAD differs from local $base_branch; Git results were preserved" 4
    }

    $worktreeList = Invoke-GitCommand @("-C", $repoRoot, "-c", "core.quotePath=false", "worktree", "list", "--porcelain")
    Assert-GitSuccess $worktreeList "Cannot read worktree registration after creation" 4
    $registered = $false
    foreach ($recordLine in $worktreeList.Output) {
        $recordText = [string]$recordLine
        if ($recordText.StartsWith("worktree ")) {
            $listedPath = Get-NormalizedPath $recordText.Substring(9)
            if ([string]::Equals($listedPath, $targetPath, [StringComparison]::OrdinalIgnoreCase)) {
                $registered = $true
                break
            }
        }
    }
    if (-not $registered) {
        Stop-CreateWorktree "Post-create verification failed: target is absent from git worktree list; Git results were preserved" 4
    }

    $sourceHeadAfter = Invoke-GitCommand @("-C", $repoRoot, "rev-parse", "HEAD")
    $sourceBranchAfter = Invoke-GitCommand @("-C", $repoRoot, "symbolic-ref", "--quiet", "--short", "HEAD")
    $sourceStatusAfter = Invoke-GitCommand @("-C", $repoRoot, "status", "--porcelain=v1", "--untracked-files=all")
    if (
        $sourceHeadAfter.ExitCode -ne 0 -or
        $sourceHeadAfter.Text.Trim() -cne $sourceHeadBefore.Text.Trim() -or
        $sourceBranchAfter.ExitCode -ne $sourceBranchBefore.ExitCode -or
        $sourceBranchAfter.Text.Trim() -cne $sourceBranchBefore.Text.Trim() -or
        $sourceStatusAfter.ExitCode -ne 0 -or
        $sourceStatusAfter.Text
    ) {
        Stop-CreateWorktree "Post-create verification failed: source worktree state changed; Git results were preserved" 4
    }

    $encodedTargetPath = [Uri]::EscapeDataString($targetPath)
    $desktopDeepLink = "codex://threads/new?path=$encodedTargetPath"
    $retryDeepLink = $desktopDeepLink.Replace("'", "''")
    $retryCommand = "Start-Process -FilePath '$retryDeepLink'"
    try {
        Start-Process -FilePath $desktopDeepLink -ErrorAction Stop | Out-Null
    } catch {
        [Console]::Error.WriteLine("[create-worktree] Partial success: worktree and branch were created, but Codex Desktop protocol activation failed.")
        [Console]::Error.WriteLine($_.Exception.Message)
        [Console]::Error.WriteLine("[create-worktree] Retry command: $retryCommand")
        exit 3
    }

    Write-Output "[create-worktree] Created successfully"
    Write-Output "Worktree: $targetPath"
    Write-Output "Branch: $fullBranch"
    Write-Output "Base: $baseCommit"
    exit 0
} catch {
    Stop-CreateWorktree "Unhandled error: $($_.Exception.Message)"
}
