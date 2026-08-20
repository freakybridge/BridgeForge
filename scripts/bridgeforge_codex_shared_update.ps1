#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(DontShow = $true)]
    [string]$SourceRepositoryRoot,

    [Parameter(DontShow = $true)]
    [switch]$TestNonWindows,

    [Parameter(DontShow = $true)]
    [int]$TestCrashAfterActionCount = 0,

    [Parameter(DontShow = $true)]
    [string]$TestFailAfterSwap,

    [Parameter(DontShow = $true)]
    [int]$TestHoldLockMilliseconds = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$CanonicalRemote = "https://github.com/freakybridge/BridgeForgeCodex.git"
$CanonicalBranch = "main"
$ManifestName = "bridgeforge-codex-manifest.json"
$OperationLogName = ".bridgeforge-codex-shared-update.json"
$CommandHomeName = ".bridgeforge-codex"
$CommandHomeLogName = ".bridgeforge-codex-home-update.json"
$script:PhaseTimings = [ordered]@{}
$script:UpdateTimer = [Diagnostics.Stopwatch]::StartNew()

function Complete-PhaseTiming {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][Diagnostics.Stopwatch]$Stopwatch
    )
    $Stopwatch.Stop()
    $script:PhaseTimings[$Name] = [math]::Round($Stopwatch.Elapsed.TotalMilliseconds, 1)
}

function Write-UpdateReceipt {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [string]$Commit,
        [string]$Mode,
        [int]$ActionCount = 0,
        [string]$ErrorMessage
    )
    if ($script:UpdateTimer.IsRunning) {
        $script:UpdateTimer.Stop()
    }
    $script:PhaseTimings["total"] = [math]::Round($script:UpdateTimer.Elapsed.TotalMilliseconds, 1)
    $receipt = [ordered]@{
        status = $Status
        source_commit = if ([string]::IsNullOrWhiteSpace($Commit)) { $null } else { $Commit }
        mode = if ([string]::IsNullOrWhiteSpace($Mode)) { $null } else { $Mode }
        action_count = $ActionCount
        timings_ms = $script:PhaseTimings
    }
    if (-not [string]::IsNullOrWhiteSpace($ErrorMessage)) {
        $receipt["error"] = $ErrorMessage
    }
    Write-Host "BRIDGEFORGE_CODEX_SHARED_UPDATE_RECEIPT $($receipt | ConvertTo-Json -Depth 6 -Compress)"
}

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

function Test-SafeRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path) -or [IO.Path]::IsPathRooted($Path)) {
        return $false
    }
    $parts = $Path.Replace("\", "/").Split("/")
    if ($parts.Count -eq 0) {
        return $false
    }
    foreach ($part in $parts) {
        if ([string]::IsNullOrWhiteSpace($part) -or $part -eq "." -or $part -eq "..") {
            return $false
        }
    }
    return $true
}

function Get-PathUnderRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )
    if (-not (Test-SafeRelativePath -Path $RelativePath)) {
        throw "Unsafe relative path in manifest: $RelativePath"
    }
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd("\", "/")
    $candidate = [IO.Path]::GetFullPath((Join-Path $rootFull $RelativePath))
    $prefix = $rootFull + [IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Manifest path escapes source root: $RelativePath"
    }
    return $candidate
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-TextSha256 {
    param([Parameter(Mandatory = $true)][string]$Text)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Get-SkillContentHash {
    param([Parameter(Mandatory = $true)]$Skill)
    $files = @($Skill.files)
    [Array]::Sort(
        $files,
        [Collections.Generic.Comparer[object]]::Create(
            [Comparison[object]]{
                param($left, $right)
                return [StringComparer]::Ordinal.Compare(
                    ([string]$left.target).Replace("\", "/"),
                    ([string]$right.target).Replace("\", "/")
                )
            }
        )
    )
    $lines = @()
    foreach ($file in $files) {
        $hash = ([string]$file.sha256).ToLowerInvariant()
        if ($hash.StartsWith("sha256:")) {
            $hash = $hash.Substring(7)
        }
        $target = ([string]$file.target).Replace("\", "/")
        $lines += "$target`n$hash"
    }
    return "sha256:$(Get-TextSha256 -Text (($lines -join "`n") + "`n"))"
}

function Get-DirectoryContentHash {
    param([Parameter(Mandatory = $true)][string]$Root)
    if (-not (Test-Path -LiteralPath $Root -PathType Container) -or (Test-ReparsePoint -Path $Root)) {
        throw "Managed skill directory is missing or is a reparse point: $Root"
    }
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd("\", "/")
    $lines = @()
    foreach ($file in @(Get-ChildItem -LiteralPath $rootFull -File -Recurse -Force)) {
        if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Managed skill file may not be a reparse point: $($file.FullName)"
        }
        $relative = $file.FullName.Substring($rootFull.Length + 1).Replace("\", "/")
        $lines += "$relative`n$(Get-Sha256 -Path $file.FullName)"
    }
    [Array]::Sort($lines, [StringComparer]::Ordinal)
    return "sha256:$(Get-TextSha256 -Text (($lines -join "`n") + "`n"))"
}

function Assert-DirectoryContentHash {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Context
    )
    if ((Get-DirectoryContentHash -Root $Path) -ne $Expected.ToLowerInvariant()) {
        throw "$Context content verification failed: $Path"
    }
}

function Enter-UpdateMutex {
    param([Parameter(Mandatory = $true)][string]$UserProfile)
    $name = "Local\BridgeForgeCodex.SharedSkillUpdate.$(Get-TextSha256 -Text $UserProfile)"
    $mutex = New-Object Threading.Mutex($false, $name)
    try {
        $acquired = $mutex.WaitOne(0)
    }
    catch [Threading.AbandonedMutexException] {
        $acquired = $true
    }
    if (-not $acquired) {
        $mutex.Dispose()
        throw "Another bridgeforge-codex shared-skill update is already running for this user."
    }
    return $mutex
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    try {
        $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
        Assert-JsonUniqueObjectKeys -Json $raw -Path $Path
        return $raw | ConvertFrom-Json
    }
    catch {
        throw "Invalid JSON file '$Path': $($_.Exception.Message)"
    }
}

function Assert-JsonUniqueObjectKeys {
    param(
        [Parameter(Mandatory = $true)][string]$Json,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $frames = New-Object System.Collections.ArrayList
    $index = 0
    while ($index -lt $Json.Length) {
        $character = $Json[$index]
        if ($character -eq '{') {
            [void]$frames.Add(@{ kind = "object"; keys = @{} })
            $index += 1
            continue
        }
        if ($character -eq '[') {
            [void]$frames.Add(@{ kind = "array" })
            $index += 1
            continue
        }
        if ($character -eq '}' -or $character -eq ']') {
            if ($frames.Count -gt 0) {
                $frames.RemoveAt($frames.Count - 1)
            }
            $index += 1
            continue
        }
        if ($character -ne '"') {
            $index += 1
            continue
        }

        $start = $index
        $index += 1
        $closed = $false
        while ($index -lt $Json.Length) {
            if ($Json[$index] -eq '\') {
                $index += 2
                continue
            }
            if ($Json[$index] -eq '"') {
                $closed = $true
                $index += 1
                break
            }
            $index += 1
        }
        if (-not $closed) {
            throw "Invalid JSON file '$Path': unterminated string."
        }
        $probe = $index
        while ($probe -lt $Json.Length -and [char]::IsWhiteSpace($Json[$probe])) {
            $probe += 1
        }
        if ($probe -ge $Json.Length -or $Json[$probe] -ne ':') {
            continue
        }
        if ($frames.Count -eq 0 -or $frames[$frames.Count - 1].kind -ne "object") {
            throw "Invalid JSON file '$Path': property key outside an object."
        }
        $token = $Json.Substring($start, $index - $start)
        $key = [string]($token | ConvertFrom-Json)
        $keys = $frames[$frames.Count - 1].keys
        if ($keys.ContainsKey($key)) {
            throw "Invalid JSON file '$Path': duplicate JSON key '$key'."
        }
        $keys[$key] = $true
    }
}

function Assert-ExactJsonProperties {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string[]]$Expected,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $actual = @($Value.PSObject.Properties | ForEach-Object { [string]$_.Name })
    $missing = @($Expected | Where-Object { $actual -cnotcontains $_ })
    $extra = @($actual | Where-Object { $Expected -cnotcontains $_ })
    if ($missing.Count -gt 0 -or $extra.Count -gt 0 -or $actual.Count -ne $Expected.Count) {
        throw "$Label fields are not exact."
    }
}

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $temporary = "$Path.tmp-$PID-$([Guid]::NewGuid().ToString('N'))"
    try {
        $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temporary -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Assert-Repository {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [switch]$SkipFetch
    )
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "Source repository does not exist: $Root"
    }
    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd("\") + "\"
    $repositoryFull = [IO.Path]::GetFullPath($Root).TrimEnd("\")
    if (-not $repositoryFull.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Source repository must be a clean clone under the system temporary directory."
    }
    $remote = ((Invoke-Git -WorkingDirectory $Root -Arguments @("config", "--get", "remote.origin.url")) -join "").Trim()
    if ((Get-NormalizedRemote $remote) -ne (Get-NormalizedRemote $CanonicalRemote)) {
        throw "Source repository origin is not the canonical bridgeforge-codex remote."
    }
    if (-not $SkipFetch) {
        Invoke-Git -WorkingDirectory $Root -Arguments @(
            "fetch",
            "--no-tags",
            "--prune",
            "origin",
            "+refs/heads/main:refs/remotes/origin/main"
        ) | Out-Null
    }
    $branch = ((Invoke-Git -WorkingDirectory $Root -Arguments @("symbolic-ref", "--short", "HEAD")) -join "").Trim()
    if ($branch -ne $CanonicalBranch) {
        throw "Source repository must have main checked out; found '$branch'."
    }
    $commit = ((Invoke-Git -WorkingDirectory $Root -Arguments @("rev-parse", "HEAD")) -join "").Trim().ToLowerInvariant()
    if ($commit -notmatch "^[0-9a-f]{40}$") {
        throw "Source repository HEAD is not a full commit SHA."
    }
    $remoteCommit = ((
        Invoke-Git -WorkingDirectory $Root -Arguments @("rev-parse", "refs/remotes/origin/main")
    ) -join "").Trim().ToLowerInvariant()
    if ($remoteCommit -notmatch "^[0-9a-f]{40}$" -or $commit -ne $remoteCommit) {
        throw "Source repository HEAD does not match the fetched canonical origin/main."
    }
    if (Test-Path -LiteralPath (Join-Path $Root ".gitmodules")) {
        throw "Submodules are not allowed in the shared-skill source."
    }
    $gitlinks = @(
        Invoke-Git -WorkingDirectory $Root -Arguments @("ls-files", "--stage") |
            Where-Object { [string]$_ -match "^160000\s" }
    )
    if ($gitlinks.Count -gt 0) {
        throw "Submodules are not allowed in the shared-skill source."
    }
    $changes = @(
        Invoke-Git -WorkingDirectory $Root -Arguments @(
            "-c", "core.excludesFile=$(Join-Path $Root '.git\info\exclude')",
            "status", "--porcelain", "--untracked-files=all"
        )
    )
    if ($changes.Count -gt 0) {
        throw "Source repository clone is not clean."
    }
    return $commit
}

function Get-PlatformConfig {
    param(
        [Parameter(Mandatory = $true)][string]$Platform,
        [Parameter(Mandatory = $true)][string]$UserProfile
    )
    if ($Platform -eq "codex") {
        return @{
            skills_root = Join-Path $UserProfile ".codex\skills"
            ledger = Join-Path $UserProfile ".codex\bridgeforge-codex-managed.json"
            manifest_target = "~/.codex/skills"
        }
    }
    throw "Unsupported platform in manifest: $Platform"
}

function Get-PlatformManifest {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$Platform
    )
    $property = $Manifest.platforms.PSObject.Properties[$Platform]
    if ($null -eq $property) {
        throw "Manifest is missing platform '$Platform'."
    }
    return $property.Value
}

function Assert-Manifest {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$UserProfile,
        [switch]$ValidateSources
    )
    $manifestPath = Join-Path $RepositoryRoot $ManifestName
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "Missing root distribution manifest: $ManifestName"
    }
    $manifest = Read-JsonFile -Path $manifestPath
    Assert-ExactJsonProperties `
        -Value $manifest `
        -Expected @("schema_version", "canonical_remote", "branch", "platforms") `
        -Label "Manifest top-level"
    if ([int]$manifest.schema_version -ne 1) {
        throw "Unsupported bridgeforge-codex manifest schema."
    }
    if ((Get-NormalizedRemote ([string]$manifest.canonical_remote)) -ne (Get-NormalizedRemote $CanonicalRemote)) {
        throw "Manifest product remote does not match the installer contract."
    }
    if ([string]$manifest.branch -ne $CanonicalBranch) {
        throw "Manifest branch does not match main."
    }
    Assert-ExactJsonProperties -Value $manifest.platforms -Expected @("codex") -Label "Manifest platforms"

    foreach ($platform in @("codex")) {
        $platformManifest = Get-PlatformManifest -Manifest $manifest -Platform $platform
        Assert-ExactJsonProperties `
            -Value $platformManifest `
            -Expected @("target", "skills") `
            -Label "Manifest platform '$platform'"
        $config = Get-PlatformConfig -Platform $platform -UserProfile $UserProfile
        if ([string]$platformManifest.target -ne $config.manifest_target) {
            throw "Manifest target for $platform is not the fixed user skill directory."
        }
        $names = @{}
        foreach ($skill in @($platformManifest.skills)) {
            Assert-ExactJsonProperties `
                -Value $skill `
                -Expected @("name", "files") `
                -Label "Manifest skill"
            $name = [string]$skill.name
            if ($name -cnotmatch "^[a-z0-9][a-z0-9-]*$") {
                throw "Unsafe skill name in manifest: $name"
            }
            $nameKey = $name.ToLowerInvariant()
            if ($names.ContainsKey($nameKey)) {
                throw "Duplicate skill name in $platform manifest: $name"
            }
            $names[$nameKey] = $true
            $targets = @{}
            $files = @($skill.files)
            if ($files.Count -eq 0) {
                throw "Skill '$name' has no files in the manifest."
            }
            foreach ($file in $files) {
                Assert-ExactJsonProperties `
                    -Value $file `
                    -Expected @("source", "target", "sha256") `
                    -Label "Manifest file for '$name'"
                $source = [string]$file.source
                $target = [string]$file.target
                if (
                    $source.Contains("\") -or $target.Contains("\") -or
                    $source.IndexOfAny([char[]]@('*', '?', '[')) -ge 0 -or
                    $target.IndexOfAny([char[]]@('*', '?', '[')) -ge 0 -or
                    -not (Test-SafeRelativePath $source) -or
                    -not (Test-SafeRelativePath $target)
                ) {
                    throw "Unsafe file path in manifest skill '$name'."
                }
                $targetKey = $target.Replace("\", "/").ToLowerInvariant()
                if ($targets.ContainsKey($targetKey)) {
                    throw "Duplicate target path in manifest skill '$name': $target"
                }
                $targets[$targetKey] = $true
                $sourcePath = Get-PathUnderRoot -Root $RepositoryRoot -RelativePath $source
                $declaredHash = [string]$file.sha256
                if ($declaredHash -cnotmatch "^sha256:[0-9a-f]{64}$") {
                    throw "Invalid SHA-256 in manifest for '$source'."
                }
                $expected = $declaredHash.Substring(7)
                if ($ValidateSources) {
                    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
                        throw "Manifest source file is missing: $source"
                    }
                    if ((Get-Sha256 -Path $sourcePath) -ne $expected) {
                        throw "Manifest SHA-256 mismatch for '$source'."
                    }
                }
            }
        }
        if ($platform -eq "codex" -and -not $names.ContainsKey("bridgeforge-codex")) {
            throw "Codex must distribute the bridgeforge-codex command bundle."
        }
    }
    return @{
        value = $manifest
        path = $manifestPath
        hash = "sha256:$(Get-Sha256 -Path $manifestPath)"
    }
}

function Read-Ledger {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Platform
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    $ledger = Read-JsonFile -Path $Path
    if ([int]$ledger.schema_version -ne 1 -or [string]$ledger.platform -ne $Platform -or $null -eq $ledger.records) {
        throw "Invalid managed ledger for ${platform}: $Path"
    }
    foreach ($property in $ledger.records.PSObject.Properties) {
        $name = $property.Name
        $record = $property.Value
        if ($name -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]*$" -or
            [string]$record.source_commit -notmatch "^[0-9a-f]{40}$" -or
            [string]$record.content_hash -notmatch "^sha256:[0-9a-f]{64}$" -or
            [string]::IsNullOrWhiteSpace([string]$record.installed_at)) {
            throw "Invalid record '$name' in managed ledger for $platform."
        }
    }
    $consentsProperty = $ledger.PSObject.Properties["consents"]
    if ($null -ne $consentsProperty) {
        if ($Platform -ne "codex") {
            throw "Managed ledger consents are only valid for codex: $Path"
        }
        $consents = $consentsProperty.Value
        $names = @($consents.PSObject.Properties | ForEach-Object { $_.Name })
        $nativeConsent = $consents.native_memories
        $validNativeConsent = $false
        if ($nativeConsent -is [string]) {
            $validNativeConsent = ([string]$nativeConsent -in @("approved", "declined"))
        }
        elseif ($null -ne $nativeConsent) {
            $consentNames = @($nativeConsent.PSObject.Properties | ForEach-Object { $_.Name } | Sort-Object)
            $expectedConsentNames = @(
                "auto_hook_maintenance",
                "decision",
                "policy_version",
                "remote",
                "repository",
                "require_private",
                "scope",
                "sync_mode"
            )
            $remoteText = [string]$nativeConsent.remote
            $normalizedRemote = $remoteText.Trim().TrimEnd([char[]]"/\\").ToLowerInvariant()
            if ($normalizedRemote.EndsWith(".git")) {
                $normalizedRemote = $normalizedRemote.Substring(0, $normalizedRemote.Length - 4)
            }
            $remoteMatchesRepository = (
                $normalizedRemote.EndsWith("/bridgeforge-codex-memories") -or
                $normalizedRemote.EndsWith(":bridgeforge-codex-memories")
            )
            $validNativeConsent = (
                @(Compare-Object -ReferenceObject $expectedConsentNames -DifferenceObject $consentNames).Count -eq 0 -and
                [string]$nativeConsent.decision -in @("approved", "declined") -and
                [int]$nativeConsent.policy_version -eq 1 -and
                [string]$nativeConsent.scope -eq "~/.codex/memories/**" -and
                [string]$nativeConsent.sync_mode -eq "bidirectional" -and
                [bool]$nativeConsent.auto_hook_maintenance -and
                [string]$nativeConsent.repository -eq "bridgeforge-codex-memories" -and
                [bool]$nativeConsent.require_private -and
                (
                    ([string]$nativeConsent.decision -eq "approved" -and
                        -not [string]::IsNullOrWhiteSpace($remoteText) -and
                        $remoteMatchesRepository) -or
                    ([string]$nativeConsent.decision -eq "declined" -and
                        $null -eq $nativeConsent.remote)
                )
            )
        }
        if ($names.Count -ne 1 -or $names[0] -ne "native_memories" -or -not $validNativeConsent) {
            throw "Invalid managed ledger consents for ${platform}: $Path"
        }
    }
    return $ledger
}

function Test-ReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $item = Get-Item -LiteralPath $Path -Force
    return (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
}

function Assert-WriteAccess {
    param([Parameter(Mandatory = $true)][string]$Path)
    $cursor = $Path
    while (-not (Test-Path -LiteralPath $cursor -PathType Container)) {
        if (Test-Path -LiteralPath $cursor) {
            throw "Target path component exists but is not a directory: $cursor"
        }
        $parent = Split-Path -Parent $cursor
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $cursor) {
            throw "No existing parent available for write preflight: $Path"
        }
        $cursor = $parent
    }
    $probe = Join-Path $cursor ".bridgeforge-codex-write-probe-$PID-$([Guid]::NewGuid().ToString('N'))"
    try {
        [IO.File]::WriteAllText($probe, "probe")
    }
    catch {
        throw "Target directory is not writable: $Path"
    }
    finally {
        if (Test-Path -LiteralPath $probe) {
            Remove-Item -LiteralPath $probe -Force
        }
    }
}

function Assert-NoReparseUnderProfile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$UserProfile
    )
    $profileFull = [IO.Path]::GetFullPath($UserProfile).TrimEnd("\")
    $cursor = [IO.Path]::GetFullPath($Path).TrimEnd("\")
    if (-not ($cursor.Equals($profileFull, [StringComparison]::OrdinalIgnoreCase) -or
        $cursor.StartsWith($profileFull + "\", [StringComparison]::OrdinalIgnoreCase))) {
        throw "User-level target escapes USERPROFILE: $Path"
    }
    while ($cursor.Length -ge $profileFull.Length) {
        if ((Test-Path -LiteralPath $cursor) -and (Test-ReparsePoint -Path $cursor)) {
            throw "User-level target path may not traverse a junction or symbolic link: $cursor"
        }
        if ($cursor.Equals($profileFull, [StringComparison]::OrdinalIgnoreCase)) {
            break
        }
        $cursor = Split-Path -Parent $cursor
    }
}

function Get-LedgerNames {
    param($Ledger)
    if ($null -eq $Ledger) {
        return @()
    }
    return @($Ledger.records.PSObject.Properties | ForEach-Object { $_.Name })
}

function Get-LedgerRecord {
    param($Ledger, [Parameter(Mandatory = $true)][string]$Name)
    if ($null -eq $Ledger) {
        return $null
    }
    $property = @($Ledger.records.PSObject.Properties | Where-Object { $_.Name -ieq $Name })
    if ($property.Count -eq 0) {
        return $null
    }
    return $property[0].Value
}

function New-UpdatePlan {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$UserProfile,
        [Parameter(Mandatory = $true)][string]$OperationId,
        [Parameter(Mandatory = $true)][string]$Commit
    )
    $platformPlans = @()
    foreach ($platform in @("codex")) {
        $config = Get-PlatformConfig -Platform $platform -UserProfile $UserProfile
        $platformManifest = Get-PlatformManifest -Manifest $Manifest -Platform $platform
        $ledger = Read-Ledger -Path $config.ledger -Platform $platform
        $managedNames = @(Get-LedgerNames -Ledger $ledger)
        $managed = @{}
        foreach ($name in $managedNames) {
            $managed[$name.ToLowerInvariant()] = $true
        }
        $managedContentHashes = @{}
        foreach ($name in $managedNames) {
            $key = $name.ToLowerInvariant()
            $target = Join-Path $config.skills_root $name
            if (-not (Test-Path -LiteralPath $target)) {
                continue
            }
            if (Test-ReparsePoint -Path $target) {
                throw "Managed skill target may not be a junction or symbolic link: $target"
            }
            $actual = Get-DirectoryContentHash -Root $target
            $record = Get-LedgerRecord -Ledger $ledger -Name $name
            if ($null -eq $record -or [string]$record.content_hash -ne $actual) {
                throw "Managed skill content drifted outside bridgeforge-codex: $platform/${name}: $target"
            }
            $managedContentHashes[$key] = $actual
        }
        $manifestNames = @{}
        $ledgerNeedsUpdate = $false
        $preservedConsents = $null
        if ($platform -eq "codex" -and $null -ne $ledger -and
            $null -ne $ledger.PSObject.Properties["consents"]) {
            $preservedConsents = [ordered]@{
                native_memories = $ledger.consents.native_memories
            }
        }
        foreach ($skill in @($platformManifest.skills)) {
            $name = [string]$skill.name
            $manifestNames[$name.ToLowerInvariant()] = $true
            $target = Join-Path $config.skills_root $name
            if ((Test-Path -LiteralPath $target) -and -not $managed.ContainsKey($name.ToLowerInvariant())) {
                throw "Unmanaged skill conflict for $platform/${name}: $target"
            }
            if ((Test-Path -LiteralPath $target) -and (Test-ReparsePoint -Path $target)) {
                throw "Managed skill target may not be a junction or symbolic link: $target"
            }
        }
        $actions = @()
        foreach ($name in $managedNames | Sort-Object) {
            if (-not $manifestNames.ContainsKey($name.ToLowerInvariant())) {
                $ledgerNeedsUpdate = $true
                $target = Join-Path $config.skills_root $name
                if ((Test-Path -LiteralPath $target) -and (Test-ReparsePoint -Path $target)) {
                    throw "Managed skill target may not be a junction or symbolic link: $target"
                }
                $hadOriginal = [bool](Test-Path -LiteralPath $target)
                $originalHash = if ($hadOriginal) {
                    $managedContentHashes[$name.ToLowerInvariant()]
                }
                else {
                    $null
                }
                $actions += [ordered]@{
                    kind = "remove"
                    name = $name
                    target = $target
                    stage = $null
                    backup = Join-Path $config.skills_root ".$name.bridgeforge-codex-backup-$OperationId"
                    had_original = $hadOriginal
                    original_content_hash = $originalHash
                    status = "pending"
                }
            }
        }
        $upserts = @($platformManifest.skills | Sort-Object @{ Expression = { if ([string]$_.name -eq "bridgeforge-codex") { 1 } else { 0 } } }, name)
        foreach ($skill in $upserts) {
            $name = [string]$skill.name
            $target = Join-Path $config.skills_root $name
            $hadOriginal = [bool](Test-Path -LiteralPath $target)
            $originalHash = if ($hadOriginal) {
                $managedContentHashes[$name.ToLowerInvariant()]
            }
            else {
                $null
            }
            $desiredHash = Get-SkillContentHash -Skill $skill
            $ledgerRecord = Get-LedgerRecord -Ledger $ledger -Name $name
            if ($hadOriginal -and $null -ne $ledgerRecord -and
                [string]$ledgerRecord.content_hash -eq $desiredHash -and
                $originalHash -eq $desiredHash) {
                if ([string]$ledgerRecord.source_commit -ne $Commit) {
                    $ledgerNeedsUpdate = $true
                }
                continue
            }
            $ledgerNeedsUpdate = $true
            $actions += [ordered]@{
                kind = "upsert"
                name = $name
                target = $target
                stage = Join-Path $config.skills_root ".$name.bridgeforge-codex-stage-$OperationId"
                backup = Join-Path $config.skills_root ".$name.bridgeforge-codex-backup-$OperationId"
                had_original = $hadOriginal
                original_content_hash = $originalHash
                status = "pending"
            }
        }
        Assert-NoReparseUnderProfile -Path $config.skills_root -UserProfile $UserProfile
        Assert-NoReparseUnderProfile -Path (Split-Path -Parent $config.ledger) -UserProfile $UserProfile
        Assert-WriteAccess -Path $config.skills_root
        Assert-WriteAccess -Path (Split-Path -Parent $config.ledger)
        $platformPlans += [ordered]@{
            platform = $platform
            skills_root = $config.skills_root
            ledger = $config.ledger
            ledger_stage = "$($config.ledger).stage-$OperationId"
            ledger_backup = "$($config.ledger).backup-$OperationId"
            ledger_had_original = [bool](Test-Path -LiteralPath $config.ledger)
            ledger_needs_update = $ledgerNeedsUpdate
            ledger_status = "pending"
            preserved_consents = $preservedConsents
            actions = $actions
        }
    }
    return $platformPlans
}

function Assert-OperationPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root
    )
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd("\", "/")
    $pathFull = [IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($rootFull + "\", [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe path in recovery log: $Path"
    }
}

function Remove-SafeTree {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    if (Test-ReparsePoint -Path $Path) {
        throw "Refusing to recursively remove a reparse point: $Path"
    }
    Remove-Item -LiteralPath $Path -Recurse -Force
}

function Restore-InterruptedOperation {
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][string]$UserProfile
    )
    if (-not (Test-Path -LiteralPath $LogPath)) {
        return
    }
    $log = Read-JsonFile -Path $LogPath
    if ([int]$log.schema_version -ne 1 -or [string]::IsNullOrWhiteSpace([string]$log.operation_id)) {
        throw "Invalid bridgeforge-codex shared update recovery log."
    }
    $operationId = [string]$log.operation_id
    if ($operationId -notmatch "^[0-9a-f]{32}$") {
        throw "Invalid operation identifier in recovery log."
    }
    $seenPlatforms = @{}
    foreach ($platformPlan in @($log.platforms)) {
        $platform = [string]$platformPlan.platform
        if ($seenPlatforms.ContainsKey($platform)) {
            throw "Duplicate platform in recovery log: $platform"
        }
        $seenPlatforms[$platform] = $true
        $config = Get-PlatformConfig -Platform $platform -UserProfile $UserProfile
        $expectedLedgerStage = "$($config.ledger).stage-$operationId"
        $expectedLedgerBackup = "$($config.ledger).backup-$operationId"
        if ([string]$platformPlan.skills_root -ne $config.skills_root -or
            [string]$platformPlan.ledger -ne $config.ledger -or
            [string]$platformPlan.ledger_stage -ne $expectedLedgerStage -or
            [string]$platformPlan.ledger_backup -ne $expectedLedgerBackup) {
            throw "Recovery log contains unexpected paths for platform '$platform'."
        }
        foreach ($action in @($platformPlan.actions)) {
            $name = [string]$action.name
            $kind = [string]$action.kind
            if ($name -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]*$" -or $kind -notin @("upsert", "remove")) {
                throw "Recovery log contains an invalid skill action."
            }
            $expectedTarget = Join-Path $config.skills_root $name
            $expectedBackup = Join-Path $config.skills_root ".$name.bridgeforge-codex-backup-$operationId"
            $expectedStage = if ($kind -eq "upsert") {
                Join-Path $config.skills_root ".$name.bridgeforge-codex-stage-$operationId"
            }
            else {
                $null
            }
            if ([string]$action.target -ne $expectedTarget -or
                [string]$action.backup -ne $expectedBackup -or
                [string]$action.stage -ne [string]$expectedStage) {
                throw "Recovery log contains unexpected paths for '$platform/$name'."
            }
            $originalHash = [string]$action.original_content_hash
            if (([bool]$action.had_original -and $originalHash -notmatch "^sha256:[0-9a-f]{64}$") -or
                (-not [bool]$action.had_original -and -not [string]::IsNullOrWhiteSpace($originalHash))) {
                throw "Recovery log lacks a valid original content hash for '$platform/$name'."
            }
        }
        if ([bool]$log.committed) {
            foreach ($action in @($platformPlan.actions)) {
                foreach ($temporary in @([string]$action.stage, [string]$action.backup)) {
                    if (-not [string]::IsNullOrWhiteSpace($temporary)) {
                        Assert-OperationPath -Path $temporary -Root $config.skills_root
                        Remove-SafeTree -Path $temporary
                    }
                }
            }
            foreach ($temporary in @([string]$platformPlan.ledger_stage, [string]$platformPlan.ledger_backup)) {
                if (-not [string]::IsNullOrWhiteSpace($temporary)) {
                    Assert-OperationPath -Path $temporary -Root (Split-Path -Parent $config.ledger)
                    if (Test-Path -LiteralPath $temporary) {
                        Remove-Item -LiteralPath $temporary -Force
                    }
                }
            }
            continue
        }

        foreach ($action in @($platformPlan.actions) | Sort-Object -Property name -Descending) {
            Assert-OperationPath -Path ([string]$action.target) -Root $config.skills_root
            Assert-OperationPath -Path ([string]$action.backup) -Root $config.skills_root
            if (-not [string]::IsNullOrWhiteSpace([string]$action.stage)) {
                Assert-OperationPath -Path ([string]$action.stage) -Root $config.skills_root
                Remove-SafeTree -Path ([string]$action.stage)
            }
            if ([bool]$action.had_original) {
                if (Test-Path -LiteralPath ([string]$action.backup)) {
                    Assert-DirectoryContentHash `
                        -Path ([string]$action.backup) `
                        -Expected ([string]$action.original_content_hash) `
                        -Context "Recovery backup for $platform/$([string]$action.name)"
                    Remove-SafeTree -Path ([string]$action.target)
                    Move-Item -LiteralPath ([string]$action.backup) -Destination ([string]$action.target)
                }
                elseif (-not (Test-Path -LiteralPath ([string]$action.target) -PathType Container) -or
                    (Get-DirectoryContentHash -Root ([string]$action.target)) -ne [string]$action.original_content_hash) {
                    throw "Recovery backup is missing and the original target cannot be verified for $platform/$([string]$action.name)."
                }
            }
            else {
                Remove-SafeTree -Path ([string]$action.target)
                Remove-SafeTree -Path ([string]$action.backup)
            }
        }
        Assert-OperationPath -Path ([string]$platformPlan.ledger_backup) -Root (Split-Path -Parent $config.ledger)
        if ([bool]$platformPlan.ledger_had_original) {
            if (Test-Path -LiteralPath ([string]$platformPlan.ledger_backup)) {
                if (Test-Path -LiteralPath $config.ledger) {
                    Remove-Item -LiteralPath $config.ledger -Force
                }
                Move-Item -LiteralPath ([string]$platformPlan.ledger_backup) -Destination $config.ledger
            }
        }
        elseif (Test-Path -LiteralPath $config.ledger) {
            Remove-Item -LiteralPath $config.ledger -Force
        }
        if (Test-Path -LiteralPath ([string]$platformPlan.ledger_stage)) {
            Remove-Item -LiteralPath ([string]$platformPlan.ledger_stage) -Force
        }
    }
    if (-not $seenPlatforms.ContainsKey("codex") -or $seenPlatforms.Count -ne 1) {
        throw "Recovery log must contain exactly the codex platform."
    }
    Remove-Item -LiteralPath $LogPath -Force
}

function Copy-SkillToStage {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)]$Skill,
        [Parameter(Mandatory = $true)][string]$Stage
    )
    Remove-SafeTree -Path $Stage
    New-Item -ItemType Directory -Path $Stage -Force | Out-Null
    foreach ($file in @($Skill.files)) {
        $source = Get-PathUnderRoot -Root $RepositoryRoot -RelativePath ([string]$file.source)
        $target = Get-PathUnderRoot -Root $Stage -RelativePath ([string]$file.target)
        $parent = Split-Path -Parent $target
        if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Copy-Item -LiteralPath $source -Destination $target
    }
    Assert-DirectoryContentHash `
        -Path $Stage `
        -Expected (Get-SkillContentHash -Skill $Skill) `
        -Context "Staged content for $($Skill.name)"
}

function Assert-PlatformTargets {
    param(
        [Parameter(Mandatory = $true)]$PlatformManifest,
        [Parameter(Mandatory = $true)][string]$SkillsRoot,
        [Parameter(Mandatory = $true)][string]$Platform
    )
    foreach ($skill in @($PlatformManifest.skills)) {
        $target = Join-Path $SkillsRoot ([string]$skill.name)
        Assert-DirectoryContentHash `
            -Path $target `
            -Expected (Get-SkillContentHash -Skill $skill) `
            -Context "Installed content for $Platform/$([string]$skill.name)"
    }
}

function New-LedgerValue {
    param(
        [Parameter(Mandatory = $true)][string]$Platform,
        [Parameter(Mandatory = $true)]$PlatformManifest,
        [Parameter(Mandatory = $true)][string]$Commit,
        $PreservedConsents
    )
    $records = [ordered]@{}
    $installedAt = [DateTime]::UtcNow.ToString("o")
    foreach ($skill in @($PlatformManifest.skills) | Sort-Object -Property name) {
        $records[[string]$skill.name] = [ordered]@{
            source_commit = $Commit
            content_hash = Get-SkillContentHash -Skill $skill
            installed_at = $installedAt
        }
    }
    $ledger = [ordered]@{
        schema_version = 1
        platform = $Platform
        records = $records
    }
    if ($Platform -eq "codex" -and $null -ne $PreservedConsents) {
        $ledger.consents = [ordered]@{
            native_memories = $PreservedConsents.native_memories
        }
    }
    return $ledger
}

function Invoke-UpdateTransaction {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$Commit,
        [Parameter(Mandatory = $true)][string]$ManifestHash,
        [Parameter(Mandatory = $true)][string]$UserProfile,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][string]$OperationId,
        [Parameter(Mandatory = $true)]$PlatformPlans
    )
    $log = [ordered]@{
        schema_version = 1
        operation_id = $OperationId
        source_commit = $Commit
        manifest_hash = $ManifestHash
        started_at = [DateTime]::UtcNow.ToString("o")
        committed = $false
        platforms = $PlatformPlans
    }
    Write-JsonAtomic -Path $LogPath -Value $log
    $completedActionCount = 0

    try {
        foreach ($platformPlan in $PlatformPlans) {
            $platformManifest = Get-PlatformManifest -Manifest $Manifest -Platform ([string]$platformPlan.platform
            )
            $platformActionCount = 0
            $skillByName = @{}
            foreach ($skill in @($platformManifest.skills)) {
                $skillByName[[string]$skill.name] = $skill
            }
            if (-not (Test-Path -LiteralPath ([string]$platformPlan.skills_root) -PathType Container)) {
                New-Item -ItemType Directory -Path ([string]$platformPlan.skills_root) -Force | Out-Null
            }
            foreach ($action in @($platformPlan.actions)) {
                if ([string]$action.kind -eq "upsert") {
                    Copy-SkillToStage -RepositoryRoot $RepositoryRoot -Skill $skillByName[[string]$action.name] -Stage ([string]$action.stage)
                }
                if (Test-Path -LiteralPath ([string]$action.backup)) {
                    throw "Unexpected transaction backup already exists: $($action.backup)"
                }
                $targetExists = [bool](Test-Path -LiteralPath ([string]$action.target) -PathType Container)
                if ($targetExists -ne [bool]$action.had_original) {
                    throw "Managed target changed after planning: $($action.target)"
                }
                if ([bool]$action.had_original) {
                    Assert-DirectoryContentHash `
                        -Path ([string]$action.target) `
                        -Expected ([string]$action.original_content_hash) `
                        -Context "Pre-swap target for $([string]$platformPlan.platform)/$([string]$action.name)"
                    Move-Item -LiteralPath ([string]$action.target) -Destination ([string]$action.backup)
                    Assert-DirectoryContentHash `
                        -Path ([string]$action.backup) `
                        -Expected ([string]$action.original_content_hash) `
                        -Context "Transaction backup for $([string]$platformPlan.platform)/$([string]$action.name)"
                }
                if ([string]$action.kind -eq "upsert") {
                    Move-Item -LiteralPath ([string]$action.stage) -Destination ([string]$action.target)
                    Assert-DirectoryContentHash `
                        -Path ([string]$action.target) `
                        -Expected (Get-SkillContentHash -Skill $skillByName[[string]$action.name]) `
                        -Context "Post-swap target for $([string]$platformPlan.platform)/$([string]$action.name)"
                }
                $action.status = "complete"
                Write-JsonAtomic -Path $LogPath -Value $log
                $completedActionCount += 1
                $platformActionCount += 1
                $failurePoint = "$([string]$platformPlan.platform):$platformActionCount"
                if (-not [string]::IsNullOrWhiteSpace($TestFailAfterSwap) -and
                    $TestFailAfterSwap -eq $failurePoint) {
                    throw "Injected test failure after swap $failurePoint; completed global actions: $completedActionCount."
                }
                if ($TestCrashAfterActionCount -gt 0 -and
                    $completedActionCount -ge $TestCrashAfterActionCount) {
                    [Environment]::Exit(91)
                }
            }
        }

        foreach ($platformPlan in $PlatformPlans) {
            $platformManifest = Get-PlatformManifest -Manifest $Manifest -Platform ([string]$platformPlan.platform)
            $ledgerValue = New-LedgerValue `
                -Platform ([string]$platformPlan.platform) `
                -PlatformManifest $platformManifest `
                -Commit $Commit `
                -PreservedConsents $platformPlan.preserved_consents
            Write-JsonAtomic -Path ([string]$platformPlan.ledger_stage) -Value $ledgerValue
        }
        foreach ($platformPlan in $PlatformPlans) {
            if (Test-Path -LiteralPath ([string]$platformPlan.ledger)) {
                Move-Item -LiteralPath ([string]$platformPlan.ledger) -Destination ([string]$platformPlan.ledger_backup)
            }
            Move-Item -LiteralPath ([string]$platformPlan.ledger_stage) -Destination ([string]$platformPlan.ledger)
            $platformPlan.ledger_status = "complete"
            Write-JsonAtomic -Path $LogPath -Value $log
        }
        foreach ($platformPlan in $PlatformPlans) {
            $platform = [string]$platformPlan.platform
            Assert-PlatformTargets `
                -PlatformManifest (Get-PlatformManifest -Manifest $Manifest -Platform $platform) `
                -SkillsRoot ([string]$platformPlan.skills_root) `
                -Platform $platform
        }
        $log.committed = $true
        Write-JsonAtomic -Path $LogPath -Value $log
        Restore-InterruptedOperation -LogPath $LogPath -UserProfile $UserProfile
    }
    catch {
        $failure = $_
        try {
            Restore-InterruptedOperation -LogPath $LogPath -UserProfile $UserProfile
        }
        catch {
            Write-Error "Shared skill update failed and automatic recovery also failed: $($_.Exception.Message)"
        }
        throw $failure
    }
}

function New-CanonicalClone {
    $root = Join-Path ([IO.Path]::GetTempPath()) "bridgeforge-codex-shared-$([Guid]::NewGuid().ToString('N'))"
    Invoke-Git -Arguments @(
        "clone",
        "--branch", $CanonicalBranch,
        "--single-branch",
        "--depth", "1",
        "--filter=blob:none",
        "--sparse",
        "--no-recurse-submodules",
        $CanonicalRemote,
        $root
    ) | Out-Null
    return $root
}

function Get-RepositoryIdentity {
    param([Parameter(Mandatory = $true)][string]$Root)
    if (-not (Test-Path -LiteralPath $Root -PathType Container) -or
        (Test-ReparsePoint -Path $Root)) {
        throw "bridgeforge-codex command home is missing or unsafe: $Root"
    }
    $remote = ((Invoke-Git -WorkingDirectory $Root -Arguments @(
        "config", "--get", "remote.origin.url"
    )) -join "").Trim()
    if ((Get-NormalizedRemote $remote) -ne (Get-NormalizedRemote $CanonicalRemote)) {
        throw "bridgeforge-codex command home origin is not canonical: $Root"
    }
    $commit = ((Invoke-Git -WorkingDirectory $Root -Arguments @(
        "rev-parse", "HEAD"
    )) -join "").Trim().ToLowerInvariant()
    if ($commit -notmatch "^[0-9a-f]{40}$") {
        throw "bridgeforge-codex command home HEAD is invalid: $Root"
    }
    $changes = @(
        Invoke-Git -WorkingDirectory $Root -Arguments @(
            "-c", "core.excludesFile=$(Join-Path $Root '.git\info\exclude')",
            "status", "--porcelain", "--untracked-files=all"
        )
    )
    if ($changes.Count -gt 0) {
        throw "bridgeforge-codex command home contains local changes: $Root"
    }
    return [ordered]@{ remote = $remote; commit = $commit }
}

function New-CommandHomePlan {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$UserProfile,
        [Parameter(Mandatory = $true)][string]$OperationId,
        [Parameter(Mandatory = $true)][string]$Commit
    )
    $target = Join-Path $UserProfile $CommandHomeName
    $homeStem = $CommandHomeName.TrimStart(".")
    $stage = Join-Path $UserProfile ".$homeStem-stage-$OperationId"
    $backup = Join-Path $UserProfile ".$homeStem-backup-$OperationId"
    $log = Join-Path $UserProfile $CommandHomeLogName
    Assert-NoReparseUnderProfile -Path $target -UserProfile $UserProfile
    Assert-WriteAccess -Path $target
    if ((Test-Path -LiteralPath $stage) -or (Test-Path -LiteralPath $backup)) {
        throw "bridgeforge-codex command-home transaction path already exists."
    }
    $hadOriginal = [bool](Test-Path -LiteralPath $target -PathType Container)
    if ((Test-Path -LiteralPath $target) -and -not $hadOriginal) {
        throw "bridgeforge-codex command home target is not a directory: $target"
    }
    if ($hadOriginal) {
        $identity = Get-RepositoryIdentity -Root $target
        if ([string]$identity.commit -eq $Commit) {
            return [ordered]@{
                target = $target
                stage = $stage
                backup = $backup
                log = $log
                operation_id = $OperationId
                had_original = $true
                needs_swap = $false
                status = "current"
            }
        }
    }
    Copy-Item -LiteralPath $SourceRoot -Destination $stage -Recurse -Force
    $stagedIdentity = Get-RepositoryIdentity -Root $stage
    if ([string]$stagedIdentity.commit -ne $Commit) {
        Remove-SafeTree -Path $stage
        throw "Staged bridgeforge-codex command home commit verification failed."
    }
    return [ordered]@{
        target = $target
        stage = $stage
        backup = $backup
        log = $log
        operation_id = $OperationId
        had_original = $hadOriginal
        needs_swap = $true
        status = "staged"
    }
}

function Install-CommandHome {
    param([Parameter(Mandatory = $true)]$Plan)
    if (-not [bool]$Plan.needs_swap) {
        return
    }
    try {
        $Plan.status = "prepared"
        Write-JsonAtomic -Path ([string]$Plan.log) -Value $Plan
        if ([bool]$Plan.had_original) {
            Move-Item -LiteralPath ([string]$Plan.target) -Destination ([string]$Plan.backup)
            $Plan.status = "backed_up"
            Write-JsonAtomic -Path ([string]$Plan.log) -Value $Plan
        }
        Move-Item -LiteralPath ([string]$Plan.stage) -Destination ([string]$Plan.target)
        $Plan.status = "installed"
        Write-JsonAtomic -Path ([string]$Plan.log) -Value $Plan
    }
    catch {
        if ((Test-Path -LiteralPath ([string]$Plan.target)) -and
            -not [bool]$Plan.had_original) {
            Remove-SafeTree -Path ([string]$Plan.target)
        }
        if ((Test-Path -LiteralPath ([string]$Plan.backup)) -and
            -not (Test-Path -LiteralPath ([string]$Plan.target))) {
            Move-Item -LiteralPath ([string]$Plan.backup) -Destination ([string]$Plan.target)
        }
        if (Test-Path -LiteralPath ([string]$Plan.stage)) {
            Remove-SafeTree -Path ([string]$Plan.stage)
        }
        if (Test-Path -LiteralPath ([string]$Plan.log)) {
            Remove-Item -LiteralPath ([string]$Plan.log) -Force
        }
        throw
    }
}

function Undo-CommandHome {
    param([Parameter(Mandatory = $true)]$Plan)
    if ([string]$Plan.status -eq "installed") {
        if (Test-Path -LiteralPath ([string]$Plan.target)) {
            Remove-SafeTree -Path ([string]$Plan.target)
        }
        if ([bool]$Plan.had_original -and (Test-Path -LiteralPath ([string]$Plan.backup))) {
            Move-Item -LiteralPath ([string]$Plan.backup) -Destination ([string]$Plan.target)
        }
    }
    elseif ([string]$Plan.status -eq "staged" -and
        (Test-Path -LiteralPath ([string]$Plan.stage))) {
        Remove-SafeTree -Path ([string]$Plan.stage)
    }
    if (Test-Path -LiteralPath ([string]$Plan.log)) {
        Remove-Item -LiteralPath ([string]$Plan.log) -Force
    }
}

function Complete-CommandHome {
    param([Parameter(Mandatory = $true)]$Plan)
    if (-not [bool]$Plan.needs_swap) {
        return
    }
    $Plan.status = "committed"
    Write-JsonAtomic -Path ([string]$Plan.log) -Value $Plan
    if (Test-Path -LiteralPath ([string]$Plan.backup) -PathType Container) {
        Remove-SafeTree -Path ([string]$Plan.backup)
    }
    Remove-Item -LiteralPath ([string]$Plan.log) -Force
}

function Restore-CommandHomeOperation {
    param([Parameter(Mandatory = $true)][string]$UserProfile)
    $logPath = Join-Path $UserProfile $CommandHomeLogName
    if (-not (Test-Path -LiteralPath $logPath)) {
        return
    }
    $value = Read-JsonFile -Path $logPath
    $operationId = [string]$value.operation_id
    if ($operationId -notmatch "^[0-9a-f]{32}$") {
        throw "Invalid bridgeforge-codex command-home recovery log."
    }
    $stem = $CommandHomeName.TrimStart(".")
    $target = Join-Path $UserProfile $CommandHomeName
    $stage = Join-Path $UserProfile ".$stem-stage-$operationId"
    $backup = Join-Path $UserProfile ".$stem-backup-$operationId"
    if ([string]$value.target -ne $target -or [string]$value.stage -ne $stage -or
        [string]$value.backup -ne $backup) {
        throw "Command-home recovery log contains unexpected paths."
    }
    $status = [string]$value.status
    if ($status -eq "committed") {
        if (-not (Test-Path -LiteralPath $target -PathType Container)) {
            throw "Committed command-home recovery is missing the installed target."
        }
        if (Test-Path -LiteralPath $backup) {
            Remove-SafeTree -Path $backup
        }
    }
    elseif ($status -eq "installed") {
        if (Test-Path -LiteralPath $target) {
            Remove-SafeTree -Path $target
        }
        if ([bool]$value.had_original) {
            if (-not (Test-Path -LiteralPath $backup -PathType Container)) {
                throw "Command-home rollback backup is missing."
            }
            Move-Item -LiteralPath $backup -Destination $target
        }
    }
    elseif ($status -eq "backed_up") {
        if (-not (Test-Path -LiteralPath $backup -PathType Container) -or
            (Test-Path -LiteralPath $target)) {
            throw "Command-home backup state is inconsistent."
        }
        Move-Item -LiteralPath $backup -Destination $target
    }
    elseif ($status -ne "prepared") {
        throw "Unknown command-home recovery status: $status"
    }
    if (Test-Path -LiteralPath $stage) {
        Remove-SafeTree -Path $stage
    }
    Remove-Item -LiteralPath $logPath -Force
}

function Invoke-Main {
    Assert-Windows
    $userProfile = [string]$env:USERPROFILE
    if ([string]::IsNullOrWhiteSpace($userProfile) -or -not (Test-Path -LiteralPath $userProfile -PathType Container)) {
        throw "USERPROFILE is not a valid existing directory."
    }
    $mutex = Enter-UpdateMutex -UserProfile $userProfile
    try {
        if ($TestHoldLockMilliseconds -gt 0) {
            Start-Sleep -Milliseconds $TestHoldLockMilliseconds
        }
        $logPath = Join-Path $userProfile $OperationLogName
        $phase = [Diagnostics.Stopwatch]::StartNew()
        Restore-CommandHomeOperation -UserProfile $userProfile
        Restore-InterruptedOperation -LogPath $logPath -UserProfile $userProfile
        Complete-PhaseTiming -Name "recovery" -Stopwatch $phase

        $cloneRoot = $null
        $commandHomePlan = $null
        $commit = $null
        $resultMode = $null
        $actionCount = 0
        try {
            $phase = [Diagnostics.Stopwatch]::StartNew()
            if ([string]::IsNullOrWhiteSpace($SourceRepositoryRoot)) {
                $cloneRoot = New-CanonicalClone
                $repositoryRoot = $cloneRoot
            }
            else {
                $repositoryRoot = [IO.Path]::GetFullPath($SourceRepositoryRoot)
            }
            $commit = Assert-Repository -Root $repositoryRoot -SkipFetch:($null -ne $cloneRoot)
            if ($cloneRoot) {
                Invoke-Git -WorkingDirectory $repositoryRoot -Arguments @(
                    "-c", "core.autocrlf=false", "sparse-checkout", "disable"
                ) | Out-Null
            }
            $manifestResult = Assert-Manifest `
                -RepositoryRoot $repositoryRoot `
                -UserProfile $userProfile `
                -ValidateSources
            Complete-PhaseTiming -Name "source_probe" -Stopwatch $phase

            $operationId = [Guid]::NewGuid().ToString("N")
            $commandHomePlan = New-CommandHomePlan `
                -SourceRoot $repositoryRoot `
                -UserProfile $userProfile `
                -OperationId $operationId `
                -Commit $commit
            $phase = [Diagnostics.Stopwatch]::StartNew()
            $platformPlans = @(
                New-UpdatePlan `
                    -Manifest $manifestResult.value `
                    -UserProfile $userProfile `
                    -OperationId $operationId `
                    -Commit $commit
            )
            $actionCount = @(
                $platformPlans | ForEach-Object { @($_.actions).Count }
            ) | Measure-Object -Sum | Select-Object -ExpandProperty Sum
            if ([bool]$commandHomePlan.needs_swap) {
                $actionCount += 1
            }
            $needsTransaction = [bool]($actionCount -gt 0 -or @(
                $platformPlans | Where-Object { [bool]$_.ledger_needs_update }
            ).Count -gt 0)
            Complete-PhaseTiming -Name "target_plan" -Stopwatch $phase

            $needsTransaction = [bool]($needsTransaction -or [bool]$commandHomePlan.needs_swap)
            if (-not $needsTransaction) {
                Write-Host "bridgeforge-codex shared skills already current at commit $commit."
                $resultMode = "noop"
            }
            else {
                $phase = [Diagnostics.Stopwatch]::StartNew()
                try {
                    Install-CommandHome -Plan $commandHomePlan
                    Invoke-UpdateTransaction `
                        -RepositoryRoot $repositoryRoot `
                        -Manifest $manifestResult.value `
                        -Commit $commit `
                        -ManifestHash $manifestResult.hash `
                        -UserProfile $userProfile `
                        -LogPath $logPath `
                        -OperationId $operationId `
                        -PlatformPlans $platformPlans
                    Complete-CommandHome -Plan $commandHomePlan
                }
                catch {
                    Undo-CommandHome -Plan $commandHomePlan
                    throw
                }
                Complete-PhaseTiming -Name "transaction" -Stopwatch $phase
                Write-Host "bridgeforge-codex shared skills updated to commit $commit."
                $resultMode = "updated"
            }
        }
        finally {
            $phase = [Diagnostics.Stopwatch]::StartNew()
            if ($null -ne $commandHomePlan -and
                [string]$commandHomePlan.status -eq "staged") {
                Undo-CommandHome -Plan $commandHomePlan
            }
            if ($cloneRoot -and (Test-Path -LiteralPath $cloneRoot)) {
                Remove-SafeTree -Path $cloneRoot
            }
            Complete-PhaseTiming -Name "cleanup" -Stopwatch $phase
        }
        Write-UpdateReceipt `
            -Status "completed" `
            -Commit $commit `
            -Mode $resultMode `
            -ActionCount $actionCount
    }
    finally {
        $mutex.ReleaseMutex()
        $mutex.Dispose()
    }
}

try {
    Invoke-Main
    exit 0
}
catch {
    Write-UpdateReceipt -Status "failed" -Mode "failed" -ErrorMessage $_.Exception.Message
    Write-Error $_.Exception.Message
    exit 1
}
