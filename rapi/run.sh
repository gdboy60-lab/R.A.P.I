#!/usr/bin/env bash
# R.A.P.I 서버 실행 (Mac/Linux, GitHub Codespaces)
# 사용법: 저장소 폴더에서  bash run.sh
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -c "import fastapi, uvicorn" 2>/dev/null || .venv/bin/python -m pip install -r requirements.txt
echo "서버 시작: http://127.0.0.1:8000  (끄려면 Ctrl + C)"
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0
