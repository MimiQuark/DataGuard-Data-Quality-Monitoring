$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = if ($env:PYTHON_EXE) { $env:PYTHON_EXE } else { "python" }

Push-Location $ProjectRoot
try {
    & $Python "src\sample_data_generator.py"
    & $Python "src\cli.py" --config "config\rules.json" --output-dir "output" --db "output\dq_history.sqlite" --no-fail
    & $Python "-m" "unittest" "discover" "-s" "tests" "-v"
}
finally {
    Pop-Location
}