param(
    [Parameter(Mandatory = $true)]
    [string]$Branch
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & git @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference
    if ($exitCode -ne 0) {
        throw "git $($Arguments -join ' ') failed: $output"
    }
    return $output
}

function Get-RepositoryRoot {
    $root = Invoke-Git @("rev-parse", "--show-toplevel")
    return ($root | Select-Object -First 1).Trim()
}

function Assert-CurrentBranch {
    param([Parameter(Mandatory = $true)][string]$ExpectedBranch)

    $actualBranch = (Invoke-Git @("branch", "--show-current") | Select-Object -First 1).Trim()
    if ($actualBranch -ne $ExpectedBranch) {
        throw "Current branch is '$actualBranch', expected '$ExpectedBranch'. Switch to the phase branch first."
    }
}

function Assert-CleanWorktree {
    $status = Invoke-Git @("status", "--porcelain")
    if ($status) {
        throw "Worktree is dirty. Commit and push intended changes before handoff."
    }
}

function Assert-GithubRemote {
    $remotes = Invoke-Git @("remote")
    if ($remotes -notcontains "github") {
        throw "Remote 'github' is missing. Add the correct remote before handoff."
    }
}

function Get-FullSha {
    param([Parameter(Mandatory = $true)][string]$Revision)
    return (Invoke-Git @("rev-parse", $Revision) | Select-Object -First 1).Trim()
}

function Assert-HeadMatchesRemote {
    param([Parameter(Mandatory = $true)][string]$BranchName)

    $localHead = Get-FullSha "HEAD"
    $remoteHead = Get-FullSha "github/$BranchName"
    if ($localHead -ne $remoteHead) {
        throw "Local HEAD $localHead does not match github/$BranchName $remoteHead. Push or fast-forward before handoff."
    }
}

function Assert-GitCommitExists {
    param([Parameter(Mandatory = $true)][string]$Commit)

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & git rev-parse --verify --quiet "$Commit^{commit}" > $null 2> $null
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference
    if ($exitCode -ne 0) {
        throw "HANDOFF Work commit '$Commit' does not exist. Update docs/development/HANDOFF.md."
    }
}

function Assert-GitCommitIsAncestor {
    param([Parameter(Mandatory = $true)][string]$Commit)

    & git merge-base --is-ancestor $Commit HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "HANDOFF Work commit '$Commit' is not an ancestor of current HEAD. Update docs/development/HANDOFF.md."
    }
}

function Assert-HandoffOnlyChangesHandoff {
    param([Parameter(Mandatory = $true)][string]$WorkCommit)

    $diffFiles = Invoke-Git @("diff", "--name-only", "$WorkCommit..HEAD")
    $diffFiles = $diffFiles | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() }
    foreach ($file in $diffFiles) {
        $normalized = $file -replace "\\", "/"
        if ($normalized -ne "docs/development/HANDOFF.md") {
            throw "HEAD differs from Work commit '$WorkCommit' in more than just HANDOFF.md: $normalized. Only docs/development/HANDOFF.md may change after the work commit."
        }
    }
}

function Read-HandoffFields {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path $Path)) {
        throw "docs/development/HANDOFF.md is missing. Create it before handoff."
    }

    $fields = @{}
    Get-Content $Path | ForEach-Object {
        if ($_ -match "^([^:#][^:]+):\s*(.*)$") {
            $fields[$Matches[1].Trim()] = $Matches[2].Trim()
        }
    }
    return $fields
}

function Read-PhaseFields {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path $Path)) {
        throw "docs/development/CURRENT_PHASE.md is missing. Create it before handoff."
    }

    $fields = @{}
    Get-Content $Path | ForEach-Object {
        if ($_ -match "^([^:#][^:]+):\s*(.*)$") {
            $fields[$Matches[1].Trim()] = $Matches[2].Trim()
        }
    }
    return $fields
}

function Read-ContractBranchPrefixes {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path $Path)) {
        throw "docs/architecture/architecture-contract.json is missing. Cannot verify branch prefix."
    }

    $raw = Get-Content $Path -Raw
    $json = $raw | ConvertFrom-Json
    return $json.branch_prefixes
}

function Assert-HandoffMatchesRepository {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Fields,
        [Parameter(Mandatory = $true)][string]$BranchName
    )

    if ($Fields["Branch"] -ne $BranchName) {
        throw "HANDOFF Branch is '$($Fields["Branch"])', expected '$BranchName'. Update docs/development/HANDOFF.md."
    }
    if ($Fields["Worktree"] -ne "clean") {
        throw "HANDOFF Worktree must be clean. Update docs/development/HANDOFF.md after committing."
    }
    if (-not $Fields.ContainsKey("Work commit") -or -not $Fields["Work commit"]) {
        throw "HANDOFF Work commit is missing. Update docs/development/HANDOFF.md."
    }
    if ($Fields.Values | Where-Object { $_ -match "pending" }) {
        throw "HANDOFF contains a pending placeholder. Replace it before handoff."
    }
    $workCommit = $Fields["Work commit"]
    if ($workCommit -notmatch "^[0-9a-f]{40}$") {
        throw "HANDOFF Work commit must be a full 40-character SHA."
    }
    Assert-GitCommitExists $workCommit
    Assert-GitCommitIsAncestor $workCommit
    Assert-HandoffOnlyChangesHandoff $workCommit
}

function Assert-WriterBranchCrossCheck {
    param(
        [Parameter(Mandatory = $true)][hashtable]$HandoffFields,
        [Parameter(Mandatory = $true)][hashtable]$PhaseFields,
        [Parameter(Mandatory = $true)][string]$BranchName,
        [Parameter(Mandatory = $true)][object]$BranchPrefixes
    )

    # 1. HANDOFF Branch == actual git branch == CURRENT_PHASE Current branch
    $phaseBranch = $PhaseFields["Current branch"]
    if ($phaseBranch -ne $BranchName) {
        throw "CURRENT_PHASE Current branch is '$phaseBranch', expected '$BranchName'."
    }

    # 2. HANDOFF Writer == CURRENT_PHASE Current writer
    $handoffWriter = $HandoffFields["Writer"]
    $phaseWriter = $PhaseFields["Current writer"]
    if (-not $handoffWriter) {
        throw "HANDOFF does not contain a 'Writer:' field."
    }
    if (-not $phaseWriter) {
        throw "CURRENT_PHASE does not contain a 'Current writer:' field."
    }
    if ($handoffWriter -ne $phaseWriter) {
        throw "HANDOFF Writer '$handoffWriter' != CURRENT_PHASE Current writer '$phaseWriter'."
    }

    # 3. Writer must be registered
    $writer = $phaseWriter
    $prefixEntry = $BranchPrefixes.PSObject.Properties | Where-Object { $_.Name -eq $writer }
    if (-not $prefixEntry) {
        throw "Writer '$writer' is not registered in architecture-contract.json branch_prefixes."
    }
    $prefix = $prefixEntry.Value

    # 4. Research branch type — special non-implementation branch
    if ($BranchName -match "^research/") {
        if ($BranchName -notmatch "^research/[^/]+$") {
            throw "Research branch '$BranchName' must match research/<non-empty slug>."
        }
        $phaseType = $PhaseFields["Phase type"]
        if (-not $phaseType) {
            throw "Research branch '$BranchName' requires CURRENT_PHASE field 'Phase type: non-implementation research'. Field is missing."
        }
        if ($phaseType -ne "non-implementation research") {
            throw "Research branch '$BranchName' requires CURRENT_PHASE 'Phase type: non-implementation research'. Got '$phaseType'."
        }
        return
    }

    # 5. Non-research branch: must match writer's implementation prefix
    if ($prefix -match "<name>") {
        # human/<name>/phase-<phase>-<slug>
        # Name must be non-empty and NOT start with 'phase-' (rejects human/phase-bot/phase-...)
        if ($BranchName -notmatch "^human/(?!phase-)[^/]+/phase-[^/]+$") {
            throw "Human branch '$BranchName' must match human/<name>/phase-<phase>-<slug>. Name must be non-empty and not start with 'phase-'."
        }
    } else {
        if (-not $BranchName.StartsWith($prefix)) {
            throw "Branch '$BranchName' does not start with prefix '$prefix' for writer '$writer'."
        }
    }
}

function Assert-NoGeneratedUntrackedArtifacts {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)

    $untracked = Invoke-Git @("ls-files", "--others", "--exclude-standard")
    $blocked = @()

    foreach ($path in $untracked) {
        $normalized = $path -replace "\\", "/"
        if (
            $normalized -eq "dist" -or
            $normalized -like "dist/*" -or
            $normalized -eq "build" -or
            $normalized -like "build/*" -or
            $normalized -like "*.egg-info/*" -or
            $normalized -like "*.egg-info" -or
            $normalized -like "*/__pycache__/*" -or
            $normalized -like "__pycache__/*" -or
            $normalized -eq ".pytest_cache" -or
            $normalized -like ".pytest_cache/*" -or
            $normalized -like ".venv/*" -or
            $normalized -like "venv/*" -or
            $normalized -like "env/*" -or
            $normalized -like ".tmp-*/*"
        ) {
            $blocked += $normalized
        }
    }

    if ($blocked.Count -gt 0) {
        throw "Generated or temporary untracked artifacts remain: $($blocked -join ', '). Remove them intentionally before handoff."
    }
}

try {
    $repoRoot = Get-RepositoryRoot
    Set-Location $repoRoot

    Assert-CurrentBranch $Branch
    Assert-CleanWorktree
    Assert-GithubRemote
    Invoke-Git @("fetch", "github") | Out-Null
    Assert-HeadMatchesRemote $Branch

    $handoffPath = Join-Path $repoRoot "docs/development/HANDOFF.md"
    $phasePath = Join-Path $repoRoot "docs/development/CURRENT_PHASE.md"
    $contractPath = Join-Path $repoRoot "docs/architecture/architecture-contract.json"

    $fields = Read-HandoffFields $handoffPath
    $phaseFields = Read-PhaseFields $phasePath
    $branchPrefixes = Read-ContractBranchPrefixes $contractPath

    Assert-HandoffMatchesRepository $fields $Branch
    Assert-WriterBranchCrossCheck $fields $phaseFields $Branch $branchPrefixes
    Assert-NoGeneratedUntrackedArtifacts $repoRoot

    $localHead = Get-FullSha "HEAD"
    $remoteHead = Get-FullSha "github/$Branch"
    Write-Host "Branch: $Branch"
    Write-Host "Writer: $($fields["Writer"])"
    Write-Host "Local HEAD: $localHead"
    Write-Host "Remote HEAD: $remoteHead"
    Write-Host "Handoff verification passed"
    exit 0
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
