# Runs the same checks CI would, locally (Windows / PowerShell).
# Usage:  pwsh -File scripts/check.ps1     (or:  .\scripts\check.ps1)
# Exit code is non-zero if any check fails, so a git hook can gate on it.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$fail = 0

function Step {
    param([string]$Name, [string]$Dir, [scriptblock]$Block)
    Write-Host "==> $Name" -ForegroundColor Cyan
    Push-Location (Join-Path $root $Dir)
    try {
        & $Block
        if ($LASTEXITCODE -ne 0) {
            Write-Host "FAILED: $Name" -ForegroundColor Red
            $script:fail = 1
        }
    }
    catch {
        Write-Host "FAILED: $Name ($_)" -ForegroundColor Red
        $script:fail = 1
    }
    finally {
        Pop-Location
    }
}

$py = ".venv\Scripts\python.exe"

Step "API: OpenAPI drift" "chumnouy_api" {
    & $py scripts\export_openapi.py | Out-Null
    git -C .. diff --exit-code -- chumnouy_api/openapi.json
}
Step "API: ruff" "chumnouy_api" { & $py -m ruff check app tests }
Step "API: pytest" "chumnouy_api" { & $py -m pytest -q }
Step "API client: drift" "packages\api-client" {
    npm run generate | Out-Null
    git -C ../.. diff --exit-code -- packages/api-client/src/schema.ts
}
Step "Web: test" "apps\web" { npm test }
Step "Web: build" "apps\web" { npm run build }

if ($fail -ne 0) {
    Write-Host "`nSome checks failed." -ForegroundColor Red
    exit 1
}
Write-Host "`nAll checks passed." -ForegroundColor Green
