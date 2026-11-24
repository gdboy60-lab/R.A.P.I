-- R.A.P.I 데이터베이스 스키마 (SQLite)
-- 규칙 명세서 9장 기준, 20개 테이블
-- 시각 표기: 판정용 시각은 모두 "시뮬레이션 시각" ISO 문자열 (YYYY-MM-DDTHH:MM:SS)
-- 금액 표기: 원 단위 정수

PRAGMA foreign_keys = ON;

-- =========================================================
-- 1단계: 사용자 · 프로젝트 · 계좌
-- =========================================================

-- 9-1. 사용자
CREATE TABLE users (
    user_id     INTEGER PRIMARY KEY,
    email       TEXT UNIQUE,                       -- 체험 계정은 NULL
    nickname    TEXT NOT NULL,
    is_guest    INTEGER NOT NULL DEFAULT 0 CHECK (is_guest IN (0, 1)),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))   -- 실제 시각
);

-- 9-21. 리플레이 기간 (운영자가 미리 등록)
CREATE TABLE replay_periods (
    period_id     INTEGER PRIMARY KEY,
    label         TEXT NOT NULL,                   -- 예: 상승장 A
    start_date    TEXT NOT NULL,                   -- 실제 과거 첫 개장일
    end_date      TEXT NOT NULL,
    trading_days  INTEGER NOT NULL CHECK (trading_days >= 10),
    description   TEXT                             -- 운영자 메모, 사용자에게 숨김
);

-- 9-22. 기간별 거래 종목
CREATE TABLE replay_stocks (
    period_id     INTEGER NOT NULL REFERENCES replay_periods(period_id),
    stock_code    TEXT NOT NULL,
    display_name  TEXT NOT NULL,                   -- 기본은 실제 종목명
    PRIMARY KEY (period_id, stock_code)
);

-- 9-2. 프로젝트 (+ 10-1 시뮬레이션 시계 열)
CREATE TABLE projects (
    project_id          INTEGER PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(user_id),
    period_id           INTEGER NOT NULL REFERENCES replay_periods(period_id),
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('pending', 'active', 'finished', 'terminated')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),   -- 실제 시각
    start_date          TEXT NOT NULL,             -- 리플레이 첫 개장일
    end_date            TEXT NOT NULL,             -- 리플레이 마지막 개장일
    total_trading_days  INTEGER NOT NULL CHECK (total_trading_days >= 10),
    baseline_end_date   TEXT NOT NULL,             -- 5번째 개장일
    baseline_daily_avg  REAL,                      -- BC-01 기준 일평균 (5일차 마감 후 기록)
    end_reason          TEXT,                      -- 예: 체결량 미달
    -- 시뮬레이션 시계
    current_day         INTEGER NOT NULL DEFAULT 1,     -- 몇 일차인지
    sim_now             TEXT NOT NULL,                  -- 현재 시뮬레이션 시각
    clock_status        TEXT NOT NULL DEFAULT 'pre_open'
                        CHECK (clock_status IN ('pre_open', 'running', 'paused', 'closed')),
    playback_speed      INTEGER NOT NULL DEFAULT 10 CHECK (playback_speed > 0),
    hide_dates          INTEGER NOT NULL DEFAULT 1 CHECK (hide_dates IN (0, 1)),
    last_real_tick      TEXT                            -- 시계를 마지막으로 진행시킨 실제 시각
);
-- 제약: 한 사용자는 대기·진행 중 프로젝트를 동시에 하나만 가질 수 있음 (NFR-03)
CREATE UNIQUE INDEX uq_one_live_project
    ON projects(user_id) WHERE status IN ('pending', 'active');

-- 9-3. 가상 계좌 (프로젝트와 1:1)
CREATE TABLE accounts (
    account_id    INTEGER PRIMARY KEY,
    project_id    INTEGER NOT NULL UNIQUE REFERENCES projects(project_id),
    initial_cash  INTEGER NOT NULL DEFAULT 10000000 CHECK (initial_cash = 10000000),
    cash          INTEGER NOT NULL CHECK (cash >= 0)
);

-- 9-4. 보유 종목
CREATE TABLE holdings (
    account_id  INTEGER NOT NULL REFERENCES accounts(account_id),
    stock_code  TEXT NOT NULL,
    quantity    INTEGER NOT NULL CHECK (quantity >= 0),   -- 0이 되면 거래 종료
    trade_id    INTEGER REFERENCES trades(trade_id),      -- 진행 중인 거래
    PRIMARY KEY (account_id, stock_code)
);

-- =========================================================
-- 2단계: 주문 · 체결 · 거래
-- =========================================================

-- 9-7. 거래 (첫 매수 체결 ~ 보유 0주)
CREATE TABLE trades (
    trade_id           INTEGER PRIMARY KEY,
    account_id         INTEGER NOT NULL REFERENCES accounts(account_id),
    stock_code         TEXT NOT NULL,
    plan_id            INTEGER REFERENCES plans(plan_id),
    status             TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    opened_at          TEXT NOT NULL,              -- 첫 매수 체결 시각
    closed_at          TEXT,                       -- 보유 0주가 된 매도 체결 시각
    stop_reached_at    TEXT,                       -- 손절가 최초 도달 (RM-03, PA-03)
    target_reached_at  TEXT,                       -- 목표가 최초 도달 (PA-02)
    net_buy_amount     INTEGER,                    -- 매수 금액 + 매수 수수료 (종료 시 확정)
    net_sell_amount    INTEGER,                    -- 매도 금액 - 매도 수수료 - 세금
    realized_pnl       INTEGER,                    -- BC-02 손실 판정
    realized_return    REAL                        -- PA-02 판정
);
-- 같은 계좌에서 같은 종목의 진행 중 거래는 하나뿐
CREATE UNIQUE INDEX uq_one_open_trade
    ON trades(account_id, stock_code) WHERE status = 'open';

-- 9-5. 주문 (order_id = 규칙의 Order ID)
CREATE TABLE orders (
    order_id       INTEGER PRIMARY KEY,
    account_id     INTEGER NOT NULL REFERENCES accounts(account_id),
    trade_id       INTEGER REFERENCES trades(trade_id),   -- 매수는 첫 체결 시 연결
    stock_code     TEXT NOT NULL,
    side           TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type     TEXT NOT NULL CHECK (order_type IN ('market', 'limit')),
    limit_price    INTEGER,
    quantity       INTEGER NOT NULL CHECK (quantity > 0),
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'filled', 'cancelled')),
    submitted_at   TEXT NOT NULL,                  -- PA-01 계획 인정 기준
    closed_at      TEXT,
    cancel_reason  TEXT CHECK (cancel_reason IN ('user', 'market_close')),
    CHECK ((order_type = 'limit') = (limit_price IS NOT NULL))
);

-- 9-6. 체결 (주문 하나에 여러 건 가능)
CREATE TABLE executions (
    execution_id  INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    price         INTEGER NOT NULL CHECK (price > 0),
    fee           INTEGER NOT NULL DEFAULT 0,
    tax           INTEGER NOT NULL DEFAULT 0,      -- 매도만
    executed_at   TEXT NOT NULL,                   -- 모든 규칙의 판정 시각 기준
    real_at       TEXT NOT NULL DEFAULT (datetime('now'))   -- 오류 추적용 실제 시각
);

-- =========================================================
-- 3단계: 매매 계획 · 관심 종목
-- =========================================================

-- 9-9. 관심 종목
CREATE TABLE watchlist (
    watch_id    INTEGER PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES projects(project_id),
    stock_code  TEXT NOT NULL,
    added_at    TEXT NOT NULL,                     -- 시뮬레이션 시각
    removed_at  TEXT
);
-- 같은 종목을 동시에 두 번 등록할 수 없음
CREATE UNIQUE INDEX uq_watch_active
    ON watchlist(project_id, stock_code) WHERE removed_at IS NULL;
-- 제약: 동시에 최대 20개 (NFR-03)
CREATE TRIGGER trg_watchlist_max20
BEFORE INSERT ON watchlist
WHEN NEW.removed_at IS NULL
 AND (SELECT COUNT(*) FROM watchlist
      WHERE project_id = NEW.project_id AND removed_at IS NULL) >= 20
BEGIN
    SELECT RAISE(ABORT, 'watchlist_limit_20');
END;

-- 9-10. 매매 계획 (거래와 1:1, 판정은 최초 값)
CREATE TABLE plans (
    plan_id         INTEGER PRIMARY KEY,
    trade_id        INTEGER UNIQUE REFERENCES trades(trade_id),   -- 첫 체결 시 연결
    first_order_id  INTEGER NOT NULL REFERENCES orders(order_id),
    reason          TEXT,
    target_price    INTEGER,
    stop_price      INTEGER,
    target_qty      INTEGER,
    created_at      TEXT NOT NULL                  -- 첫 매수 주문 제출 시각
);

-- 9-11. 계획 수정 이력 (AI 피드백 근거 전용)
CREATE TABLE plan_revisions (
    revision_id  INTEGER PRIMARY KEY,
    plan_id      INTEGER NOT NULL REFERENCES plans(plan_id),
    field        TEXT NOT NULL CHECK (field IN ('reason', 'target_price', 'stop_price', 'target_qty')),
    old_value    TEXT,
    new_value    TEXT,
    changed_at   TEXT NOT NULL
);

-- =========================================================
-- 4단계: 시세 · 휴장일 달력
-- =========================================================

-- 9-12. 휴장일 달력
CREATE TABLE market_calendar (
    date        TEXT PRIMARY KEY,
    is_open     INTEGER NOT NULL CHECK (is_open IN (0, 1)),
    open_time   TEXT,                              -- 예: 09:00:00 (개장일만)
    close_time  TEXT,                              -- 예: 15:30:00
    CHECK (is_open = 0 OR (open_time IS NOT NULL AND close_time IS NOT NULL))
);

-- 9-13. 일봉
CREATE TABLE daily_prices (
    stock_code  TEXT NOT NULL,
    date        TEXT NOT NULL,
    open        INTEGER NOT NULL,
    high        INTEGER NOT NULL,
    low         INTEGER NOT NULL,
    close       INTEGER NOT NULL,
    volume      INTEGER NOT NULL,
    PRIMARY KEY (stock_code, date)
);

-- 9-14. 체결 순간 시세 스냅샷
CREATE TABLE execution_snapshots (
    execution_id    INTEGER PRIMARY KEY REFERENCES executions(execution_id),
    current_price   INTEGER NOT NULL,
    prev_close      INTEGER,                       -- PA-04
    cum_volume      INTEGER,                       -- MC-02
    elapsed_ratio   REAL,                          -- MC-02
    avg_volume_20d  REAL,                          -- MC-02
    ma_20d          REAL,                          -- MC-03
    rsi_14          REAL                           -- MC-01
);

-- 9-15. 손절·목표가 도달 기록 (거래마다 종류별 최대 1건)
CREATE TABLE price_touches (
    touch_id    INTEGER PRIMARY KEY,
    trade_id    INTEGER NOT NULL REFERENCES trades(trade_id),
    kind        TEXT NOT NULL CHECK (kind IN ('stop', 'target')),
    touched_at  TEXT NOT NULL,
    price       INTEGER NOT NULL,
    UNIQUE (trade_id, kind)
);

-- 9-16. 시세 끊김 구간 (MVP는 테이블만 생성, 13-2)
CREATE TABLE feed_gaps (
    gap_id      INTEGER PRIMARY KEY,
    stock_code  TEXT,                              -- 전체 끊김이면 NULL
    started_at  TEXT NOT NULL,
    ended_at    TEXT
);

-- =========================================================
-- 5단계: 평가 결과 · 감점 기록
-- =========================================================

-- 9-17. 규칙 판정 기록 (점수의 유일한 원본)
CREATE TABLE rule_evaluations (
    eval_id          INTEGER PRIMARY KEY,
    project_id       INTEGER NOT NULL REFERENCES projects(project_id),
    rule_id          TEXT NOT NULL,                -- 예: BC-02
    area             TEXT NOT NULL CHECK (area IN ('RM', 'PA', 'BC', 'MC')),
    target_trade_id  INTEGER REFERENCES trades(trade_id),   -- 거래 단위 규칙
    target_date      TEXT,                                   -- BC-01, BC-03 (하루 단위)
    result           TEXT NOT NULL CHECK (result IN ('violation', 'hold', 'void')),
    penalty          INTEGER NOT NULL DEFAULT 0,
    evidence         TEXT,                         -- JSON: 체결 번호, 시각, 지표 값 등
    hold_reason      TEXT,
    evaluated_at     TEXT NOT NULL,
    updated_at       TEXT,
    published        INTEGER NOT NULL DEFAULT 0 CHECK (published IN (0, 1)),  -- 장 마감 공개 여부 (10-3)
    CHECK (target_trade_id IS NOT NULL OR target_date IS NOT NULL),
    CHECK ((result = 'violation') = (penalty > 0))
);
-- 제약: 같은 프로젝트에서 규칙 + 대상 조합은 한 줄만 (중복 감점 방지, NFR-03)
CREATE UNIQUE INDEX uq_rule_target
    ON rule_evaluations(project_id, rule_id,
                        COALESCE(target_trade_id, -1), COALESCE(target_date, ''));

-- 9-18. 최종 결과 (기간 종료 시 한 번 기록)
CREATE TABLE final_results (
    project_id        INTEGER PRIMARY KEY REFERENCES projects(project_id),
    rm_score          REAL NOT NULL,
    pa_score          REAL NOT NULL,
    bc_score          REAL NOT NULL,
    mc_score          REAL NOT NULL,
    overall_score     REAL NOT NULL,
    unresolved_holds  INTEGER NOT NULL DEFAULT 0,
    finalized_at      TEXT NOT NULL
);

-- 9-19. AI 피드백 (입력과 출력을 함께 저장)
CREATE TABLE ai_feedbacks (
    feedback_id   INTEGER PRIMARY KEY,
    project_id    INTEGER NOT NULL REFERENCES projects(project_id),
    kind          TEXT NOT NULL CHECK (kind IN ('daily', 'final')),
    trading_day   INTEGER,                         -- 몇 일차 피드백인지
    input_data    TEXT NOT NULL,                   -- JSON
    output_text   TEXT,                            -- JSON (5칸 구조)
    model         TEXT,
    status        TEXT NOT NULL DEFAULT 'retrying' CHECK (status IN ('ok', 'retrying', 'failed')),
    attempts      INTEGER NOT NULL DEFAULT 0 CHECK (attempts <= 3),   -- 최초 1회 + 재시도 2회
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
