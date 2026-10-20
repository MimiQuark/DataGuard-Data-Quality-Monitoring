$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = if ($env:PYTHON_EXE) { $env:PYTHON_EXE } else { "python" }
$env:PYTHONPATH = "$ProjectRoot\src;$env:PYTHONPATH"

Push-Location $ProjectRoot
try {
    $steps = @(
        @("-m", "dataguard.sample_data_generator"),
        @("-m", "dataguard", "--config", "config\rules.json", "--output-dir", "output", "--db", "output\dq_history.sqlite", "--no-fail"),
        @("-m", "pytest", "-q")
    )
    foreach ($step in $steps) {
        Write-Host ""
        Write-Host "==> python $($step -join ' ')"
        & $Python @step
        if ($LASTEXITCODE -ne 0) {
            throw "step failed with exit code $LASTEXITCODE"
        }
    }
}
finally {
    Pop-Location
}
