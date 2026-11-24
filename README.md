# R.A.P.I

초보 투자자의 가상 매매 습관을 14개 규칙으로 평가하고 AI 피드백을 주는 모바일 웹 서비스 (수업·공모전 시연용 MVP).
설계 기준은 규칙 명세서와 PRD를 따른다.

## 처음 실행하기

깃허브에서 받은 직후에도 아래 한 줄이면 된다. 가상환경 만들기, 패키지 설치, 서버 실행을 차례로 하고,
`rapi.db` 가 없으면 서버가 처음 켜질 때 자동으로 만들어 개발용 예시 기간을 넣는다.

```bash
.\run.ps1          # Windows PowerShell
bash run.sh        # Mac / GitHub Codespaces
```

브라우저에서 http://127.0.0.1:8000 을 연다. 직접 명령으로 하려면:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1                  # Mac: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
python -m pytest -q                         # 테스트
```

Windows에서 `pip.exe`·`uvicorn.exe` 가 "애플리케이션 제어 정책"으로 막히면, 명령 앞에 항상 `python -m` 을 붙인다.
`.\run.ps1` 이 "스크립트를 실행할 수 없습니다"로 막히면 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 를 한 번 실행한다.

지금 동작하는 흐름: 로그인(체험으로 시작) → 프로젝트 시작(기간 선택) → 홈(상단 시계 바: 장 열기·일시정지·속도·장 마감까지·다음 거래일).

## 실제 일봉 데이터 넣기 (B)

1. 공공데이터포털에서 **금융위원회_주식시세정보** 활용신청 → 마이페이지에서 일반 인증키(Decoding) 복사
2. `periods.example.json` 을 복사해 `periods.json` 을 만들고 기간·종목을 고친다 (개장일 10일 이상)
3. 실행 (PowerShell)

```bash
$env:DATA_GO_KR_KEY="발급받은_인증키"
python -m app.data.load_prices periods.json
```

기간마다 시작 약 400일 전부터 일봉을 받아 `daily_prices`, `market_calendar`, `replay_periods`, `replay_stocks` 를 채운다. 기간 앞 일봉이 250일보다 적은 종목은 "주의"로 알려준다.

지킬 것: 공식 API로만 받기(크롤링 금지), `rapi.db`·`periods.json`·CSV를 깃허브에 올리지 않기(재배포 금지, `.gitignore` 에 등록됨), 화면에 출처 표시.

## 폴더 구조

| 경로 | 내용 | 1주차 담당 |
| --- | --- | --- |
| `schema.sql` | 20개 테이블과 제약. 테이블 정의의 원본 | A |
| `app/db.py` | 연결, 초기화 | A |
| `app/engine/clock.py` | 시뮬레이션 시계 (DB와 무관한 순수 계산) | A |
| `app/engine/clock_store.py` | 시계를 projects 테이블에 읽고 쓰기 | A |
| `app/projects.py` | 체험 계정, 프로젝트·계좌 만들기 | A |
| `app/rules/catalog.py` | 14개 규칙 목록(영역·감점·판정 시점), 점수 계산 | B |
| `app/seed_dev.py` | 개발용 예시 데이터 (실제 데이터가 오면 대체) | B |
| `app/main.py` | FastAPI 라우트 | C |
| `app/templates/`, `app/static/` | 화면(Jinja2), 시계 바 JS, 스타일 | C |
| `tests/` | 스키마 제약, 시계, 점수 테스트 | 모두 |

## 데이터베이스 제약 (NFR-03)

| 규칙 | 구현 |
| --- | --- |
| 사용자당 진행 중 프로젝트 1개 | `uq_one_live_project` 부분 고유 인덱스 |
| 같은 규칙 + 같은 대상 중복 감점 금지 | `uq_rule_target` 고유 인덱스 (NULL 은 COALESCE 로 처리) |
| 관심 종목 동시 20개 | `trg_watchlist_max20` 트리거 |
| 종목당 진행 중 거래 1개 | `uq_one_open_trade` 부분 고유 인덱스 |
| 위반이면 감점 > 0, 보류·무효면 0 | `rule_evaluations` CHECK |

## 시계가 동작하는 방식

- 화면이 장중에 1초마다 `GET /api/clock` 을 부르면, 서버가 "실제 경과 시간 × 배속"만큼 시계를 진행한다.
- 한 번에 인정하는 실제 시간은 최대 5초다. 그래서 앱을 닫아 호출이 끊기면 시계가 멈춘다.
- 시계는 시뮬레이션 1초마다 `on_second(t)` 콜백을 부른다. 2주차 체결 엔진(지정가 체결, 손절·목표가 도달)은 `main.py` 의 `engine_tick` 에 연결한다.
- 장 마감까지 건너뛰기도 1초씩 모두 처리한다 (하루 23,400번 콜백).

## 다음에 붙일 곳

| 주차 | 위치 |
| --- | --- |
| 2주 | `engine_tick` 에 체결 엔진 연결, `app/rules/` 에 RM·PA·BC 규칙 파일 추가 |
| 3주 | 장 마감 처리 순서(명세서 10-2)를 `control_clock`/`get_clock` 의 장 마감 시점에 연결, MC 규칙, AI 피드백 |
| 4주 | 최종 리포트 집계와 화면 |

## 참고

- 체험 계정은 브라우저 쿠키로 이어보기를 하는 시연용 단순 방식이다. 공개 서비스라면 서명된 세션으로 바꿔야 한다.
- 13-1에서 정한 SQLAlchemy는 아직 쓰지 않았다. 지금은 표준 라이브러리 `sqlite3` 로 `schema.sql` 을 그대로 쓰며, 필요해지면 같은 DB 파일에 SQLAlchemy를 연결하면 된다.
