$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Script
    )

    Write-Host "==> $Name"
    & $Script
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed"
    }
}

function Get-RepositoryRoot {
    $scriptRoot = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptRoot "..")).Path
}

$repoRoot = Get-RepositoryRoot
Set-Location $repoRoot

$venvDir = Join-Path $repoRoot ".venv"
$pythonExe = Join-Path $venvDir "Scripts/python.exe"

if (-not (Test-Path $pythonExe)) {
    Invoke-Step "Create .venv" { python -m venv $venvDir }
}

Invoke-Step "Upgrade pip" { & $pythonExe -m pip install --upgrade pip }
Invoke-Step "Install LingShu editable dev package" { & $pythonExe -m pip install -e ".[dev]" }
Invoke-Step "Import smoke" { & $pythonExe -c "import lingshu; print(lingshu.__name__)" }
Invoke-Step "CLI smoke" { & $pythonExe -m lingshu.cli.main --help | Out-Null }

Write-Host "Development environment is ready."
