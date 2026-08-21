param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("SessionStart", "Stop", "SessionEnd")]
    [string]$HookEvent
)

$ErrorActionPreference = "Stop"

if ($env:CODEX_HOME) {
    $codexRoot = $env:CODEX_HOME
} else {
    $codexRoot = Join-Path $env:USERPROFILE ".codex"
}
$hookState = Join-Path $codexRoot ".bridgeforge-codex\memory-sync"

function Write-HookReceipt {
    param([string]$Stage)

    if (-not (Test-Path -LiteralPath $hookState -PathType Container)) {
        return
    }
    $line = "handler_revision=3 event=$HookEvent stage=$Stage utc=$([DateTime]::UtcNow.ToString('o'))"
    $log = Join-Path $hookState "hook-dispatch.log"
    try {
        [IO.File]::AppendAllText(
            $log,
            $line + [Environment]::NewLine,
            [Text.UTF8Encoding]::new($false)
        )
    } catch {
        # Diagnostic logging must never change the lifecycle hook result.
    }
}

Write-HookReceipt "wrapper-start"

$gitOutput = @(& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or $gitOutput.Count -eq 0) {
    Write-HookReceipt "git-root-missing"
    exit 65
}
$projectRoot = [string]$gitOutput[0]
$hookPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $hookPython -PathType Leaf)) {
    Write-HookReceipt "project-python-missing"
    exit 66
}

$syncScript = Join-Path $PSScriptRoot "codex_memory_sync.py"
& $hookPython -B $syncScript hook-run --event $HookEvent --project-root $projectRoot
$hookExit = $LASTEXITCODE
Write-HookReceipt "python-exit-$hookExit"
exit $hookExit
