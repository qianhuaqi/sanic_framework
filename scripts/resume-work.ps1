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

function Assert-GitRepository {
    Invoke-Git @("rev-parse", "--is-inside-work-tree") | Out-Null
}

function Assert-CleanWorktree {
    $status = Invoke-Git @("status", "--porcelain")
    if ($status) {
        throw "Worktree is dirty. Commit or intentionally discard local changes before resuming on another computer."
    }
}

function Assert-GithubRemote {
    $remotes = Invoke-Git @("remote")
    if ($remotes -notcontains "github") {
        throw "Remote 'github' is missing. Add it before resuming work."
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
        throw "Local HEAD $localHead does not match github/$BranchName $remoteHead. Stop and reconcile manually."
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
        throw "HANDOFF Work commit '$Commit' does not exist. Stop before editing code."
    }
}

function Assert-GitCommitIsAncestor {
    param([Parameter(Mandatory = $true)][string]$Commit)

    & git merge-base --is-ancestor $Commit HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "HANDOFF Work commit '$Commit' is not an ancestor of current HEAD. Stop before editing code."
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
        throw "docs/development/HANDOFF.md is missing. Stop before editing code."
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
        throw "docs/development/CURRENT_PHASE.md is missing. Stop before editing code."
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

function Assert-HandoffIsValid {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Fields,
        [Parameter(Mandatory = $true)][string]$BranchName
    )

    if ($Fields["Branch"] -ne $BranchName) {
        throw "HANDOFF Branch is '$($Fields["Branch"])', expected '$BranchName'. Stop before editing code."
    }
    if ($Fields["Worktree"] -ne "clean") {
        throw "HANDOFF Worktree must be clean. Stop before editing code."
    }
    if (-not $Fields.ContainsKey("Work commit") -or -not $Fields["Work commit"]) {
        throw "HANDOFF Work commit is missing. Stop before editing code."
    }
    if ($Fields.Values | Where-Object { $_ -match "pending" }) {
        throw "HANDOFF contains a pending placeholder. Stop before editing code."
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

    $phaseBranch = $PhaseFields["Current branch"]
    if ($phaseBranch -ne $BranchName) {
        throw "CURRENT_PHASE Current branch is '$phaseBranch', expected '$BranchName'."
    }

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

    $writer = $phaseWriter
    $prefixEntry = $BranchPrefixes.PSObject.Properties | Where-Object { $_.Name -eq $writer }
    if (-not $prefixEntry) {
        throw "Writer '$writer' is not registered in architecture-contract.json branch_prefixes."
    }
    $prefix = $prefixEntry.Value

    # Research branch type — special non-implementation branch
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

    # Non-research branch: must match writer's implementation prefix
    if ($prefix -match "<name>") {
        if ($BranchName -notmatch "^human/(?!phase-)[^/]+/phase-[^/]+$") {
            throw "Human branch '$BranchName' must match human/<name>/phase-<phase>-<slug>. Name must be non-empty and not start with 'phase-'."
        }
    } else {
        if (-not $BranchName.StartsWith($prefix)) {
            throw "Branch '$BranchName' does not start with prefix '$prefix' for writer '$writer'."
        }
    }
}

function Get-CurrentPrNumber {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)

    $phaseFile = Join-Path $RepositoryRoot "docs/development/CURRENT_PHASE.md"
    if (-not (Test-Path $phaseFile)) {
        return "unknown"
    }

    $line = Get-Content $phaseFile | Where-Object { $_ -match "^Current PR:\s*(.+)$" } | Select-Object -First 1
    if ($line -match "^Current PR:\s*(.+)$") {
        return $Matches[1].Trim()
    }
    return "unknown"
}

try {
    Assert-GitRepository
    $repoRoot = Get-RepositoryRoot
    Set-Location $repoRoot

    Assert-CleanWorktree
    Assert-GithubRemote

    Invoke-Git @("fetch", "github") | Out-Null
    Invoke-Git @("switch", $Branch) | Out-Null
    Invoke-Git @("pull", "--ff-only", "github", $Branch) | Out-Null
    Assert-HeadMatchesRemote $Branch

    $currentBranch = (Invoke-Git @("branch", "--show-current") | Select-Object -First 1).Trim()
    $currentHead = Get-FullSha "HEAD"

    $handoffPath = Join-Path $repoRoot "docs/development/HANDOFF.md"
    $phasePath = Join-Path $repoRoot "docs/development/CURRENT_PHASE.md"
    $contractPath = Join-Path $repoRoot "docs/architecture/architecture-contract.json"

    $handoffFields = Read-HandoffFields $handoffPath
    $phaseFields = Read-PhaseFields $phasePath
    $branchPrefixes = Read-ContractBranchPrefixes $contractPath

    Assert-HandoffIsValid $handoffFields $Branch
    Assert-WriterBranchCrossCheck $handoffFields $phaseFields $Branch $branchPrefixes

    $prNumber = Get-CurrentPrNumber $repoRoot

    Write-Host "Current branch: $currentBranch"
    Write-Host "Current HEAD: $currentHead"
    Write-Host ""
    Write-Host "Recent commits:"
    Invoke-Git @("log", "-5", "--oneline") | ForEach-Object { Write-Host $_ }
    Write-Host ""
    Write-Host "HANDOFF.md:"
    Get-Content $handoffPath | ForEach-Object { Write-Host $_ }
    Write-Host ""
    Write-Host "Current PR: $prNumber"
    Write-Host "Before editing, read the latest GitHub PR comments and confirm there is no active [WORKING] lock."
    exit 0
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
