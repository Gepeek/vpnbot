$ErrorActionPreference = "Stop"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $python) {
    Write-Host "Python не найден. Установи Python 3.11+ с https://www.python.org/downloads/ и включи Add python.exe to PATH."
    exit 1
}

if ($python.Name -eq "py.exe" -or $python.Name -eq "py") {
    & py -m pip install -r requirements.txt
    & py -m playwright install chromium
} else {
    & python -m pip install -r requirements.txt
    & python -m playwright install chromium
}
