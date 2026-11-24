# R.A.P.I 서버 실행 (Windows PowerShell)
# 처음 실행하면 가상환경 만들기 → 패키지 설치 → 서버 실행까지 한 번에 한다.
# 사용법: 저장소 폴더에서  .\run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "가상환경을 만드는 중..."
    python -m venv .venv
}
$py = ".venv\Scripts\python.exe"

# pip.exe / uvicorn.exe 는 앱 제어 정책에 막힐 수 있어서 항상 python -m 으로 실행한다
& $py -c "import fastapi, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "패키지를 설치하는 중... (처음 한 번, 1~2분)"
    & $py -m pip install -r requirements.txt
}

Write-Host "서버 시작: http://127.0.0.1:8000  (끄려면 Ctrl + C)"
& $py -m uvicorn app.main:app --reload
