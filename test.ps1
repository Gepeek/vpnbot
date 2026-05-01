$ErrorActionPreference = "Stop"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $python) {
    Write-Host "Python не найден в PATH."
    exit 1
}

if ($python.Name -eq "py.exe" -or $python.Name -eq "py") {
    & py -m pip install -r requirements.txt
    & py -m pytest -q
} else {
    & python -m pip install -r requirements.txt
    & python -m pytest -q
}
