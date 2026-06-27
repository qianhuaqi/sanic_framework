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
    $handoffFields = Read-HandoffFields $handoffPath
    Assert-HandoffIsValid $handoffFields $Branch
    $prNumber = Get-CurrentPrNumber $repoRoot

    Write-Host "Current branch: $currentBranch"
    Write-Host "Current HEAD: $currentHead"
    Write-Host ""
    Write-Host "Recent commits:"
    Invoke-Git @("log", "-5", "--oneline") | ForEach-Object { Write-Host $_ }
    Write-Host ""
    Write-Host "HANDOFF.md:"
    if (-not (Test-Path $handoffPath)) {
        throw "docs/development/HANDOFF.md is missing. Stop before editing code."
    }
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
