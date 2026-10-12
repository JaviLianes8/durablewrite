# Local quality gate. Run before every commit. No CI runs in the cloud.
$ErrorActionPreference = "Stop"

ruff format --check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
mypy --strict src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
