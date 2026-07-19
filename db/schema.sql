-- The machine's source of truth. Typed, structured, queryable.
--
-- Belief predicates are evaluated as SQL against this, which is why the fields
-- are typed rather than stuffed into free text. `regime` and `factors` are JSONB
-- so a predicate can say  (regime->>'atr14')::numeric between 3 and 5  — something
-- no journal product's `tags String[]` can express.

CREATE TABLE IF NOT EXISTS decision (
    id             BIGSERIAL PRIMARY KEY,
    ts             TIMESTAMPTZ  NOT NULL DEFAULT now(),
    arm            TEXT         NOT NULL DEFAULT 'beliefs',   -- beliefs | control (phase 6 A/B)
    as_name        TEXT         NOT NULL,
    symbol         TEXT         NOT NULL,                     -- ICM:XAUUSD (qkt form)
    broker_symbol  TEXT,                                      -- XAUUSDm (venue form)

    action         TEXT         NOT NULL,                     -- TRADE | NO_TRADE | GATED
    side           TEXT,                                      -- BUY | SELL
    lots           NUMERIC,
    sl             NUMERIC,
    tp             NUMERIC,
    expected_rr    NUMERIC,                                   -- the model's CLAIM. Never trusted.
    conviction     NUMERIC,                                   -- recorded from day one: the
                                                              -- phase-5 calibration study needs
                                                              -- it and it cannot be backfilled.

    -- the journal proper: why
    setup          TEXT,
    factors        JSONB        NOT NULL DEFAULT '[]',
    news           JSONB        NOT NULL DEFAULT '[]',
    regime         JSONB        NOT NULL DEFAULT '{}',
    thesis         TEXT,
    rationale_md   TEXT,
    invalidation   TEXT,
    charts         TEXT[]       NOT NULL DEFAULT '{}',
    context_snapshot JSONB      NOT NULL DEFAULT '{}',       -- versioned account,
                                                              -- quote, bars, studies,
                                                              -- calendar, and exact
                                                              -- model packet

    -- which knowledge it used. This is what makes the MEMORY itself scoreable:
    -- which map nodes appear in profitable decisions? which sources were being
    -- read before the bad ones?
    map_nodes_used   TEXT[]     NOT NULL DEFAULT '{}',
    beliefs_used     TEXT[]     NOT NULL DEFAULT '{}',
    sources_read     TEXT[]     NOT NULL DEFAULT '{}',
    procedures_used  TEXT[]     NOT NULL DEFAULT '{}',
    sources_missing  TEXT[]     NOT NULL DEFAULT '{}',        -- a missing source must NEVER be
                                                              -- indistinguishable from a neutral
                                                              -- reading, or every belief
                                                              -- conditioned on it is poisoned.
    unexplained      TEXT,                                    -- the model's own "I don't get this"
                                                              -- -> becomes a RESEARCH trigger

    -- execution truth
    ticket         BIGINT UNIQUE,                             -- MT5 ticket == THE JOIN KEY
    open_deal      BIGINT,
    fill_price     NUMERIC,
    retcode        INT,
    accepted       BOOLEAN      NOT NULL DEFAULT false,
    gate_rejects   JSONB        NOT NULL DEFAULT '[]',

    -- risk at entry: the denominator of R. Stored NOW because it cannot be
    -- reconstructed after the fact (equity moves, stops get moved).
    risk_at_entry  NUMERIC,
    equity_at_entry NUMERIC,
    conviction_mult NUMERIC,

    -- provenance
    model          TEXT,
    prompt_sha     TEXT,
    canonical_dsl  TEXT,
    cmd_sha256     TEXT,
    qkt_version    TEXT
);

-- Existing demo volumes migrate in place; CREATE TABLE IF NOT EXISTS does not
-- add columns to a table created by an older checkout.
ALTER TABLE decision
    ADD COLUMN IF NOT EXISTS context_snapshot JSONB NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS decision_ts_idx     ON decision (ts);
CREATE INDEX IF NOT EXISTS decision_symbol_idx ON decision (symbol);
CREATE INDEX IF NOT EXISTS decision_action_idx ON decision (action);
CREATE INDEX IF NOT EXISTS decision_regime_idx ON decision USING GIN (regime);
CREATE INDEX IF NOT EXISTS decision_factors_idx ON decision USING GIN (factors);

-- bin/trade additionally holds a session-level Postgres advisory lock keyed by
-- symbol while a cycle is in flight. It needs no table, survives scheduler
-- replicas, and releases automatically if the process/connection dies.


CREATE TABLE IF NOT EXISTS outcome (
    ticket       BIGINT       PRIMARY KEY REFERENCES decision (ticket),
    closed_at    TIMESTAMPTZ  NOT NULL,
    close_price  NUMERIC,

    -- Aggregated across ALL deals for the position, IN and OUT. MT5 books
    -- commission on the IN deal, so summing only the OUT rows under-counts cost.
    gross_pnl    NUMERIC      NOT NULL,   -- sum(profit)
    commission   NUMERIC      NOT NULL,   -- sum(commission), as MT5 reports it (negative)
    swap         NUMERIC      NOT NULL,
    net_pnl      NUMERIC      NOT NULL,   -- gross + commission + swap
    r_multiple   NUMERIC,                 -- net_pnl / risk_at_entry. The currency of everything.

    lots_closed  NUMERIC      NOT NULL,
    duration_s   BIGINT       NOT NULL,
    deals        JSONB        NOT NULL,   -- the raw history rows, for audit
    joined_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS outcome_closed_at_idx ON outcome (closed_at);

-- Scheduler truth. Every cron invocation records start, finish, and exit state
-- so the System page can distinguish a running loop from an assumed one.
CREATE TABLE IF NOT EXISTS job_run (
    id          BIGSERIAL PRIMARY KEY,
    job         TEXT        NOT NULL,
    command     TEXT        NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    ok          BOOLEAN,
    detail      TEXT
);

CREATE INDEX IF NOT EXISTS job_run_job_started_idx
    ON job_run (job, started_at DESC);


-- Conviction calibration and belief scoring both read this derived view. Drop
-- it before recreation because adding a decision column changes d.*'s column
-- positions, which CREATE OR REPLACE VIEW deliberately refuses to guess.
DROP VIEW IF EXISTS episode;
CREATE VIEW episode AS
SELECT
    d.*,
    o.closed_at, o.close_price, o.net_pnl, o.gross_pnl, o.commission, o.swap,
    o.r_multiple, o.duration_s, o.lots_closed
FROM decision d
JOIN outcome o USING (ticket)
WHERE d.action = 'TRADE';
