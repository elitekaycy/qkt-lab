import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookOpenText,
  Bot,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleSlash2,
  CircleDollarSign,
  Clock3,
  Compass,
  Database,
  Download,
  ExternalLink,
  FileText,
  Gauge,
  LayoutDashboard,
  Layers3,
  Menu,
  Newspaper,
  Radio,
  RefreshCw,
  Route,
  Search,
  Server,
  ShieldCheck,
  Target,
  TimerReset,
  TrendingDown,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { addMonths, format, getDay, startOfMonth, subMonths } from "date-fns";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  createChart,
  LineSeries,
  LineStyle,
} from "lightweight-charts";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const PAGE_COPY = {
  overview: ["Command journal", "Portfolio overview", "Account truth, realized performance, decision activity, and recent evidence."],
  journal: ["Complete audit trail", "Decision journal", "Every execution, deliberate pass, safety block, explanation, and chart snapshot."],
  calendar: ["Day-level review", "Trading calendar", "Realized P&L and decision activity grouped by UTC trading day."],
  analytics: ["Find the repeatable edge", "Performance analytics", "Risk-adjusted outcomes by setup, hour, and decision behavior."],
  system: ["Operational truth", "System status", "Recorded loop activity, broker session, safety gates, and evidence guarantees."],
};

const NAV = [
  ["overview", "Overview", LayoutDashboard],
  ["journal", "Journal", BookOpenText],
  ["calendar", "Calendar", CalendarDays],
  ["analytics", "Analytics", BarChart3],
  ["system", "System", Activity],
];

const COLORS = {
  TRADE: "#5cb8ff",
  NO_TRADE: "#79828c",
  GATED: "#f5bd38",
};

const ACTION_META = {
  TRADE: { label: "Trade", noun: "trade", tone: "info", icon: Zap },
  NO_TRADE: { label: "Passed", noun: "pass", tone: "muted", icon: CircleSlash2 },
  GATED: { label: "Blocked", noun: "block", tone: "warning", icon: ShieldCheck },
};

async function getJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function money(value, { signed = true } = {}) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const number = Number(value);
  const sign = signed ? (number > 0 ? "+" : number < 0 ? "−" : "") : "";
  return `${sign}$${Math.abs(number).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function number(value, digits = 2) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function percent(value) {
  return value == null ? "—" : `${number(value, 1)}%`;
}

function utc(value, { dateOnly = false } = {}) {
  if (!value) return "—";
  const date = new Date(value);
  return new Intl.DateTimeFormat(undefined, dateOnly
    ? { timeZone: "UTC", year: "numeric", month: "short", day: "2-digit" }
    : {
        timeZone: "UTC", year: "numeric", month: "short", day: "2-digit",
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
      }).format(date);
}

function duration(seconds) {
  if (seconds == null) return "—";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function titleCase(value) {
  return String(value ?? "")
    .replaceAll(/[_-]+/g, " ")
    .replaceAll(/\b\w/g, (letter) => letter.toUpperCase())
    .replaceAll(/\bEma(?=\b|\d|\()/g, "EMA")
    .replaceAll(/\bRsi(?=\b|\d|\()/g, "RSI")
    .replaceAll(/\bAtr(?=\b|\d|\()/g, "ATR");
}

function humanFactor(value) {
  const [kind, ...parts] = String(value ?? "").split(":");
  const observation = titleCase(parts.join(":"));
  const labels = {
    trend: "Trend",
    trend_1h: "Hourly trend",
    entry: "Entry quality",
    entry_15m: "15-minute entry",
    session: "Session",
    calendar: "Events",
    data: "Data quality",
    spread: "Spread",
    liquidity: "Liquidity",
    level: "Key level",
  };
  return {
    label: labels[kind] ?? titleCase(kind) ?? "Observation",
    value: observation || "Recorded",
  };
}

function factorIcon(value) {
  const kind = String(value ?? "").split(":")[0];
  if (kind.startsWith("trend")) return TrendingUp;
  if (kind.startsWith("entry") || kind === "level") return Target;
  if (kind === "session") return Clock3;
  if (kind === "calendar") return CalendarDays;
  if (kind === "data") return Database;
  if (kind === "spread" || kind === "liquidity") return Gauge;
  return Compass;
}

function factorExplanation(value) {
  const exact = {
    "entry:extended-above-ema": "Price was already extended above its moving average. Entering here would chase rather than buy from a controlled location.",
    "entry:extended-below-ema": "Price was already extended below its moving average. Entering here would chase rather than sell from a controlled location.",
    "data:timestamp-mismatch": "The market timestamp did not match the decision session, so the chart could not be treated as current.",
    "session:closed-or-stale": "The venue appeared closed or inactive, making the visible price unsuitable for a new position.",
    "calendar:clear": "No confirmed high-impact event conflicted with the planned trading window.",
    "spread:normal": "The quoted spread was within the configured execution limit.",
    "session:week-open": "The market had only just reopened for the week, when liquidity and price discovery can be less dependable.",
    "liquidity:thin": "Available liquidity appeared thin, increasing the risk of noise, slippage, and unreliable follow-through.",
    "trend_1h:unreliable": "The hourly context was not current enough to confirm the larger directional structure.",
    "entry_15m:bearish-break": "The 15-minute tape broke lower, but the move lacked reliable higher-timeframe confirmation.",
    "level:ema50-break": "Price moved through the 50-period EMA, weakening the prior short-term structure.",
    "data:timeframe-stale": "At least one required timeframe was stale, so the timeframes could not be compared safely.",
  };
  if (exact[value]) return exact[value];
  const item = humanFactor(value);
  return `${item.label}: ${item.value}.`;
}

function primaryGate(row) {
  return row?.gate_rejects?.[0];
}

function decisionHeadline(row) {
  const symbol = row?.symbol?.split(":").at(-1) ?? "instrument";
  if (row?.action === "GATED") {
    return `Trade blocked — ${titleCase(primaryGate(row)?.gate || row.setup || "safety check")}`;
  }
  if (row?.action === "TRADE" && row.accepted) {
    return `${titleCase(row.side)} ${symbol} executed`;
  }
  if (row?.action === "TRADE") return "Broker refused the proposed order";
  return `No trade — ${titleCase(row?.setup || "conditions did not justify risk")}`;
}

function decisionSummary(row) {
  return primaryGate(row)?.detail
    || row?.thesis
    || row?.rationale_md
    || "No supporting explanation was recorded.";
}

function ageLabel(seconds) {
  if (seconds == null) return "No cycle recorded";
  if (seconds < 60) return "less than a minute ago";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function marketStateFor(row) {
  if (!row) return [];
  const context = row.context_snapshot ?? {};
  const indicators = context.indicators ?? {};
  const result = [];
  const seen = new Set();
  const canonical = (label) => String(label).toLowerCase().replaceAll(/[^a-z0-9]+/g, "");
  for (const [label, value] of [...Object.entries(indicators), ...Object.entries(row.regime ?? {})]) {
    if (value == null) continue;
    const key = canonical(label);
    if (seen.has(key) || (key === "atr14" && seen.has("atr14"))) continue;
    seen.add(key);
    result.push({ label, value });
  }
  return result;
}

function toneFor(value) {
  const n = Number(value);
  return n > 0 ? "text-positive" : n < 0 ? "text-negative" : "text-bright";
}

function QktMark({ className = "h-8 w-8" }) {
  return (
    <svg className={className} viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <path d="M13 11H7v26h6M35 11h6v26h-6" stroke="#a78bfa" strokeWidth="3" />
      <path d="M24 20v17" stroke="#f3f5f7" strokeWidth="3" strokeLinecap="round" />
      <circle cx="24" cy="15" r="2.6" fill="#c8f74a" />
    </svg>
  );
}

function useMediaQuery(query) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}

function StatusDot({ state = "idle", className = "" }) {
  const colors = {
    ready: "bg-positive shadow-[0_0_0_5px_rgb(63_224_140_/_10%)]",
    warn: "bg-warning shadow-[0_0_0_5px_rgb(245_189_56_/_10%)]",
    down: "bg-negative shadow-[0_0_0_5px_rgb(255_107_107_/_10%)]",
    idle: "bg-faint",
  };
  return <i aria-hidden="true" className={`inline-block h-2 w-2 shrink-0 rounded-full ${colors[state]} ${className}`} />;
}

function Sidebar({ page, setPage, collapsed, setCollapsed, mobileOpen, closeMobile, status }) {
  const gatewayReady = status?.gateway?.online && status?.gateway?.http === 200;
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const asideRef = useRef(null);
  useEffect(() => {
    if (mobileOpen && !isDesktop) {
      requestAnimationFrame(() => asideRef.current?.querySelector('[aria-current="page"]')?.focus());
    }
  }, [isDesktop, mobileOpen]);
  return (
    <>
      <button
        type="button"
        aria-label="Close navigation"
        onClick={() => closeMobile()}
        className={`fixed inset-0 top-14 z-30 bg-black/70 backdrop-blur-sm md:hidden ${mobileOpen ? "block" : "hidden"}`}
      />
      <aside
        ref={asideRef}
        id="primary-navigation"
        aria-label="Primary navigation"
        aria-hidden={!isDesktop && !mobileOpen}
        inert={!isDesktop && !mobileOpen}
        className={[
        "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-line bg-panel px-3 py-5 transition-[width,transform] duration-200",
        collapsed ? "md:w-[72px]" : "md:w-[264px]",
        "top-14 w-[264px] md:top-0",
        mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
      ].join(" ")}
      >
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-4 top-6 hidden h-8 w-8 place-items-center rounded-full border border-line-strong bg-raised text-muted hover:text-bright md:grid"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
        </button>
        <div className={`flex h-10 items-center ${collapsed ? "justify-center" : "gap-2.5 px-2"}`}>
          <QktMark className="h-8 w-8 shrink-0" />
          {!collapsed && <strong className="text-lg font-extrabold text-bright">qkt<span className="text-accent">·</span>lab</strong>}
        </div>
        <div className={`mt-5 rounded-xl border border-line bg-raised ${collapsed ? "grid h-12 place-items-center border-transparent bg-transparent" : "p-3.5"}`}>
          {collapsed ? <span title={gatewayReady ? "Gateway connected" : "Gateway unavailable"}><StatusDot state={gatewayReady ? "ready" : "down"} /><span className="sr-only">{gatewayReady ? "Gateway connected" : "Gateway unavailable"}</span></span> : (
            <>
              <span className="eyebrow">Live instance</span>
              <div className="mt-2 flex items-center gap-2 text-xs font-semibold text-bright">
                <StatusDot state={gatewayReady ? "ready" : "down"} />
                EXNESS · XAUUSD
              </div>
              <p className="mt-1.5 text-[11px] text-faint">Autonomous analyst · UTC</p>
            </>
          )}
        </div>
        <nav className="mt-5 grid gap-1" aria-label="Journal sections">
          {NAV.map(([id, label, Icon]) => (
            <button
              key={id}
              type="button"
              title={label}
              aria-current={page === id ? "page" : undefined}
              onClick={() => { setPage(id); closeMobile(false); }}
              className={[
                "flex h-10 items-center rounded-lg text-sm font-semibold transition",
                collapsed ? "justify-center px-0" : "gap-3 px-3",
                page === id ? "bg-accent text-ink" : "text-muted hover:bg-raised hover:text-body",
              ].join(" ")}
            >
              <Icon size={19} strokeWidth={1.8} />
              {!collapsed && <span>{label}</span>}
            </button>
          ))}
        </nav>
        <div className={`mt-auto border-t border-line pt-4 ${collapsed ? "flex justify-center" : "px-2"}`}>
          {collapsed ? <span title={status?.killSwitch ? "KILL engaged" : "Order gate armed"}><StatusDot state={status?.killSwitch ? "warn" : "ready"} /><span className="sr-only">{status?.killSwitch ? "KILL engaged; new orders blocked" : "Order gate armed"}</span></span> : (
            <div className="flex gap-2.5">
              <StatusDot state={status?.killSwitch ? "warn" : "ready"} className="mt-1" />
              <div>
                <p className={`text-xs font-semibold ${status?.killSwitch ? "text-warning" : "text-positive"}`}>
                  {status?.killSwitch ? "KILL engaged" : "Order gate armed"}
                </p>
                <p className="mt-1 text-[10px] leading-4 text-faint">This journal is read-only and cannot place orders.</p>
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

function Widget({ title, subtitle, action, className = "", children }) {
  return (
    <section className={`panel min-w-0 overflow-hidden ${className}`}>
      <header className="flex min-h-[62px] items-start justify-between gap-4 border-b border-line px-4 py-3.5">
        <div>
          <h2 className="text-sm font-semibold text-bright">{title}</h2>
          {subtitle && <p className="mt-1 text-[11px] text-muted">{subtitle}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

function EmptyState({ icon: Icon = BarChart3, title = "Awaiting evidence", copy }) {
  return (
    <div className="grid min-h-48 place-items-center px-6 py-10 text-center">
      <div>
        <div className="mx-auto grid h-10 w-10 place-items-center rounded-xl border border-line bg-raised text-faint">
          <Icon size={18} />
        </div>
        <p className="mt-3 text-sm font-semibold text-bright">{title}</p>
        <p className="mx-auto mt-1 max-w-sm text-xs leading-5 text-muted">{copy}</p>
      </div>
    </div>
  );
}

function MetricCard({ label, value, detail, icon: Icon, tone = "text-bright" }) {
  const iconTone = tone === "text-bright" ? "text-muted" : tone;
  return (
    <article className="panel min-w-0 p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="eyebrow">{label}</span>
        {Icon && <Icon size={15} aria-hidden="true" className={iconTone} />}
      </div>
      <strong className={`mono mt-2 block truncate text-xl font-semibold ${tone}`}>{value}</strong>
      <small className="mt-1 block min-h-8 text-[10px] leading-4 text-faint">{detail}</small>
    </article>
  );
}

function AccountWidget({ status }) {
  const body = status?.account?.body;
  const ready = status?.account?.online && status?.account?.http === 200 && body?.ok;
  const login = body?.login ? `••••${String(body.login).slice(-4)}` : "—";
  return (
    <Widget
      title="Broker account"
      subtitle="Authenticated Exness MT5 truth · USD"
      action={<span className={`flex items-center gap-2 text-[10px] font-semibold ${ready ? "text-positive" : "text-negative"}`}><StatusDot state={ready ? "ready" : "down"} />{ready ? "Connected" : "Unavailable"}</span>}
      className="lg:col-span-2"
    >
      {ready ? (
        <div className="grid grid-cols-2 divide-x divide-y divide-line sm:grid-cols-4 sm:divide-y-0">
          {[
            { label: "Balance", value: money(body.balance, { signed: false }), tone: "text-bright" },
            { label: "Equity", value: money(body.equity, { signed: false }), tone: "text-bright" },
            { label: "Free margin", value: money(body.margin_free, { signed: false }), tone: "text-bright" },
            { label: "Open P&L", value: money(body.profit), tone: toneFor(body.profit) },
          ].map((item) => (
            <div key={item.label} className="p-4">
              <span className="eyebrow">{item.label}</span>
              <strong className={`mono mt-2 block text-base ${item.tone}`}>{item.value}</strong>
            </div>
          ))}
        </div>
      ) : <EmptyState icon={Server} title="Broker account unavailable" copy="The journal will not invent balance or equity when the authenticated gateway cannot answer." />}
      {ready && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line px-4 py-3 text-[10px] text-muted">
          <span>Account <b className="mono text-body">{login}</b></span>
          <span>Server <b className="text-body">{body.server}</b></span>
          <span>Leverage <b className="mono text-body">1:{body.leverage}</b></span>
          <span>Margin <b className="mono text-body">{money(body.margin, { signed: false })}</b></span>
        </div>
      )}
    </Widget>
  );
}

function ChartTooltip({ active, payload, label, moneyValues = true }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line-strong bg-panel/95 px-3 py-2 shadow-xl backdrop-blur">
      <p className="text-[10px] text-muted">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} className="mono mt-1 text-xs" style={{ color: entry.color }}>
          {entry.name}: {moneyValues ? money(entry.value) : number(entry.value)}
        </p>
      ))}
    </div>
  );
}

function EquityWidget({ analytics }) {
  const data = analytics?.curve ?? [];
  const ending = data.at(-1)?.cumulativePnl ?? 0;
  const lineColor = ending > 0 ? "#3fe08c" : ending < 0 ? "#ff6b6b" : "#c8f74a";
  return (
    <Widget
      title="Realized P&L curve"
      subtitle="Broker-joined lab net · USD · starts at zero"
      action={<span className="mono text-[10px] text-muted">n={data.length}</span>}
      className="lg:col-span-2"
    >
      {!data.length ? (
        <EmptyState icon={TrendingUp} title="No closed trades yet" copy="The curve stays empty until a real accepted broker position closes and the joiner records its exact net result." />
      ) : (
        <div className="h-72 px-2 pb-3 pt-5">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} accessibilityLayer role="img" aria-label={`Realized cumulative profit and loss curve with ${data.length} closed trades, ending at ${money(ending)}`}>
              <defs>
                <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={lineColor} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#22272d" vertical={false} />
              <XAxis dataKey="at" tickFormatter={(v) => utc(v, { dateOnly: true })} stroke="#4e565f" tick={{ fontSize: 10 }} />
              <YAxis tickFormatter={(v) => `$${v}`} stroke="#4e565f" tick={{ fontSize: 10 }} width={55} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="cumulativePnl" name="Lab P&L" stroke={lineColor} fill="url(#equityFill)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Widget>
  );
}

function DecisionMix({ analytics }) {
  const data = analytics?.decisionBreakdown ?? [];
  const total = data.reduce((sum, item) => sum + item.count, 0);
  return (
    <Widget title="Decision mix" subtitle="Every cycle is counted, not only fills">
      {!total ? <EmptyState icon={Bot} title="No decisions" copy="The first scheduler cycle will populate this view." /> : (
        <div className="grid grid-cols-[150px_1fr] items-center gap-2 p-3">
          <div className="relative h-36">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart accessibilityLayer role="img" aria-label={`Decision mix: ${data.map((item) => `${item.count} ${ACTION_META[item.action]?.label ?? item.action}`).join(", ")}`}>
                <Pie data={data} dataKey="count" nameKey="action" innerRadius={43} outerRadius={63} stroke="none">
                  {data.map((item) => <Cell key={item.action} fill={COLORS[item.action] ?? "#79828c"} />)}
                </Pie>
                <Tooltip content={<ChartTooltip moneyValues={false} />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
              <div><strong className="mono block text-lg text-bright">{total}</strong><span className="text-[10px] uppercase tracking-wider text-faint">cycles</span></div>
            </div>
          </div>
          <div className="space-y-2">
            {data.map((item) => (
              <div key={item.action} className="flex items-center justify-between gap-3 text-xs">
                <span className="flex items-center gap-2 text-muted"><i className="h-2 w-2 rounded-full" style={{ background: COLORS[item.action] }} />{ACTION_META[item.action]?.label ?? titleCase(item.action)}</span>
                <b className="mono text-body">{item.count}</b>
              </div>
            ))}
          </div>
        </div>
      )}
    </Widget>
  );
}

function actionStyle(action, accepted) {
  if (action === "TRADE" && accepted === false) return "bg-negative/10 text-negative";
  if (action === "TRADE") return "bg-info/10 text-info";
  if (action === "GATED") return "bg-warning/10 text-warning";
  return "bg-raised text-muted";
}

function ActionPill({ action, accepted }) {
  const meta = action === "TRADE" && accepted === true
    ? { ...ACTION_META.TRADE, label: "Executed" }
    : action === "TRADE" && accepted === false
      ? { label: "Broker rejected", icon: AlertTriangle }
      : ACTION_META[action];
  const Icon = meta?.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold ${actionStyle(action, accepted)}`}>
      {Icon && <Icon size={11} strokeWidth={2.2} aria-hidden="true" />}
      {meta?.label ?? titleCase(action)}
    </span>
  );
}

function DecisionTable({ rows, onOpen, compact = false, cardView = false }) {
  if (!rows.length) return <EmptyState icon={BookOpenText} title="No matching decisions" copy="Try a different filter, or wait for the scheduler to record its next cycle." />;
  const reviewLabel = (row) => `Review decision ${row.id}: ${decisionHeadline(row)}, recorded ${utc(row.ts)} UTC`;
  return (
    <div className="overflow-auto">
      <div className={`divide-y divide-line ${cardView ? "" : "xl:hidden"}`}>
        {rows.map((row) => (
          <button
            type="button"
            key={row.id}
            aria-label={reviewLabel(row)}
            onClick={() => onOpen(row.id)}
            className="grid min-h-16 w-full grid-cols-[minmax(0,1fr)_auto] gap-3 p-4 text-left transition hover:bg-raised/60"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <ActionPill action={row.action} accepted={row.accepted} />
                <strong className="mono text-[11px] text-bright">{row.symbol?.split(":").at(-1)}</strong>
                {row.side && <span className={row.side === "BUY" ? "text-[10px] text-info" : "text-[10px] text-violet"}>{row.side}</span>}
              </div>
              <p className="mt-2 truncate text-xs font-medium text-body">{decisionHeadline(row)}</p>
              <time dateTime={row.ts} className="mono mt-1 block text-[10px] text-faint">{utc(row.ts)} UTC</time>
            </div>
            <div className="flex items-center gap-2">
              <span className={`mono text-[11px] font-semibold ${toneFor(row.net_pnl)}`}>
                {row.net_pnl != null ? money(row.net_pnl) : row.accepted ? "OPEN" : "NO POSITION"}
              </span>
              <ArrowRight size={14} className="text-faint" />
            </div>
          </button>
        ))}
      </div>
      <table className={`${cardView ? "hidden" : "hidden xl:table"} w-full min-w-[780px] border-collapse text-left text-xs`}>
        <caption className="sr-only">{compact ? "Recent trading decisions" : "Trading decision journal"}. Activate Review to open the full evidence.</caption>
        <thead>
          <tr className="border-b border-line text-[10px] uppercase tracking-[.12em] text-muted">
            <th scope="col" className="sticky top-0 bg-panel px-4 py-3 font-semibold">Time · UTC</th>
            <th scope="col" className="sticky top-0 bg-panel px-3 py-3 font-semibold">Decision</th>
            <th scope="col" className="sticky top-0 bg-panel px-3 py-3 font-semibold">Instrument</th>
            <th scope="col" className="sticky top-0 bg-panel px-3 py-3 font-semibold">Setup / reason</th>
            {!compact && <th scope="col" className="sticky top-0 bg-panel px-3 py-3 font-semibold">Risk</th>}
            <th scope="col" className="sticky top-0 bg-panel px-3 py-3 text-right font-semibold">Outcome</th>
            <th scope="col" className="sticky top-0 bg-panel px-3 py-3"><span className="sr-only">Review</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} onClick={() => onOpen(row.id)} className="group cursor-pointer border-b border-line/70 transition hover:bg-raised/60 focus-within:bg-raised/60">
              <td className="whitespace-nowrap px-4 py-3 text-[10px] text-muted"><time dateTime={row.ts} className="mono">{utc(row.ts)}</time></td>
              <td className="px-3 py-3"><ActionPill action={row.action} accepted={row.accepted} /></td>
              <td className="px-3 py-3">
                <strong className="mono block text-[11px] text-bright">{row.symbol?.split(":").at(-1)}</strong>
                <span className={row.side === "BUY" ? "text-info" : row.side === "SELL" ? "text-violet" : "text-faint"}>{row.side ?? "—"}</span>
              </td>
              <td className="max-w-[320px] px-3 py-3">
                <p className="truncate font-medium text-body">{decisionHeadline(row)}</p>
                <p className="mt-1 truncate text-[10px] text-faint">{decisionSummary(row)}</p>
              </td>
              {!compact && (
                <td className="mono px-3 py-3 text-[10px] text-muted">
                  <span className="block">{row.lots == null ? "—" : `${number(row.lots)} lots`}</span>
                  <span className="mt-1 block">{row.risk_at_entry == null ? "risk —" : `${money(row.risk_at_entry, { signed: false })} risk`}</span>
                </td>
              )}
              <td className={`mono whitespace-nowrap px-3 py-3 text-right font-semibold ${toneFor(row.net_pnl)}`}>
                {row.net_pnl != null ? money(row.net_pnl) : row.accepted ? "OPEN" : "NO POSITION"}
                {row.r_multiple != null && <small className="mt-1 block text-[10px] text-muted">{number(row.r_multiple)} R</small>}
              </td>
              <td className="px-2 py-2">
                <button
                  type="button"
                  aria-label={reviewLabel(row)}
                  onClick={(event) => { event.stopPropagation(); onOpen(row.id); }}
                  className="grid h-10 w-10 place-items-center rounded-lg text-muted hover:bg-ink hover:text-accent"
                >
                  <ArrowRight size={15} aria-hidden="true" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MiniCalendar({ entries, month, onMonth, onDay, selected, expanded = false }) {
  const first = startOfMonth(month);
  const leading = (getDay(first) + 6) % 7;
  const daysInMonth = new Date(Date.UTC(month.getUTCFullYear(), month.getUTCMonth() + 1, 0)).getUTCDate();
  const byDate = new Map(entries.map((item) => [item.date, item]));
  const monthKey = `${month.getUTCFullYear()}-${String(month.getUTCMonth() + 1).padStart(2, "0")}`;
  const monthEntries = entries.filter((item) => item.date.startsWith(monthKey));
  const monthDecisions = monthEntries.reduce((sum, item) => sum + Number(item.decisions || 0), 0);
  const monthClosed = monthEntries.reduce((sum, item) => sum + Number(item.closed_trades || 0), 0);
  const monthPnl = monthEntries.reduce((sum, item) => sum + Number(item.net_pnl || 0), 0);
  const cells = Array.from({ length: leading + daysInMonth }, (_, index) => {
    if (index < leading) return null;
    const day = index - leading + 1;
    const key = `${month.getUTCFullYear()}-${String(month.getUTCMonth() + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    return { day, key, entry: byDate.get(key) };
  });
  while (cells.length % 7) cells.push(null);
  return (
    <div>
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <button type="button" aria-label="Previous month" onClick={() => onMonth(subMonths(month, 1))} className="grid h-10 w-10 place-items-center rounded-lg text-muted hover:bg-raised hover:text-bright"><ChevronLeft size={16} aria-hidden="true" /></button>
        <strong aria-live="polite" className="text-xs text-bright">{format(month, "MMMM yyyy")} <span className="ml-1 font-normal text-faint">UTC</span></strong>
        <button type="button" aria-label="Next month" onClick={() => onMonth(addMonths(month, 1))} className="grid h-10 w-10 place-items-center rounded-lg text-muted hover:bg-raised hover:text-bright"><ChevronRight size={16} aria-hidden="true" /></button>
      </div>
      <div className="grid grid-cols-7 px-3 pt-3 text-center text-[10px] uppercase tracking-wider text-faint">
        {[
          ["Mon", "Monday"], ["Tue", "Tuesday"], ["Wed", "Wednesday"], ["Thu", "Thursday"],
          ["Fri", "Friday"], ["Sat", "Saturday"], ["Sun", "Sunday"],
        ].map(([day, full]) => <abbr key={day} title={full} className="no-underline">{day}</abbr>)}
      </div>
      <div className="grid grid-cols-7 gap-1 p-3">
        {cells.map((cell, index) => {
          if (!cell) return <span key={`empty-${index}`} />;
          if (!cell.entry) {
            return <div key={cell.key} className={`${expanded ? "min-h-24" : "aspect-square min-h-10"} rounded-lg p-1.5 text-[10px] text-faint`}>{cell.day}</div>;
          }
          const passed = Number(cell.entry.no_trades || 0);
          const blocked = Number(cell.entry.gated || 0);
          const tradeDecisions = Number(cell.entry.trade_decisions || 0);
          const closed = Number(cell.entry.closed_trades || 0);
          const description = [
            `${cell.entry.decisions || 0} decisions`,
            tradeDecisions ? `${tradeDecisions} trade decisions` : "",
            passed ? `${passed} passed` : "",
            blocked ? `${blocked} blocked` : "",
            closed ? `${closed} closed, ${money(cell.entry.net_pnl)}` : "",
          ].filter(Boolean).join(", ");
          return (
            <button
              type="button"
              key={cell.key}
              aria-label={`${utc(`${cell.key}T00:00:00Z`, { dateOnly: true })}: ${description}`}
              aria-pressed={selected === cell.key}
              onClick={() => onDay?.(cell.key)}
              className={[
                "relative flex flex-col rounded-lg border p-1.5 text-left transition",
                expanded ? "min-h-24" : "aspect-square min-h-10",
                selected === cell.key
                  ? "border-accent bg-accent/10"
                  : "border-line-strong bg-raised/70 hover:border-accent hover:bg-raised",
              ].join(" ")}
            >
              <span className={`text-[10px] ${selected === cell.key ? "font-semibold text-accent" : "text-muted"}`}>{cell.day}</span>
              <span className="mt-auto block min-w-0">
                {expanded && (
                  <span className="mb-1 block text-[10px] leading-4 text-muted">
                    {[tradeDecisions && `${tradeDecisions} trade`, passed && `${passed} passed`, blocked && `${blocked} blocked`, closed && `${closed} closed`].filter(Boolean).join(" · ")}
                  </span>
                )}
                {expanded ? (
                  <strong className={`mono block truncate text-[10px] ${closed ? toneFor(cell.entry.net_pnl) : "text-body"}`}>
                    {closed ? money(cell.entry.net_pnl) : `${cell.entry.decisions} decision${cell.entry.decisions === 1 ? "" : "s"}`}
                  </strong>
                ) : (
                  <span className={`block leading-none ${closed ? toneFor(cell.entry.net_pnl) : "text-body"}`}>
                    <strong className="mono block text-sm">{closed ? money(cell.entry.net_pnl) : cell.entry.decisions}</strong>
                    <span className="mt-1 block text-[10px] text-muted">{closed ? "net P&L" : "decisions"}</span>
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line px-4 py-3 text-[10px] text-muted">
        <span><b className="mono text-body">{monthDecisions}</b> decisions</span>
        <span><b className="mono text-body">{monthClosed}</b> closed</span>
        {monthClosed > 0 && <span className={toneFor(monthPnl)}><b className="mono">{money(monthPnl)}</b> net</span>}
        <span className="ml-auto hidden text-faint sm:inline">Select a recorded day to review it</span>
      </div>
    </div>
  );
}

function CalendarWidget({ calendar, className = "", expanded = false, onDay, selected }) {
  const latest = calendar.length ? new Date(`${calendar.at(-1).date}T00:00:00Z`) : new Date();
  const [month, setMonth] = useState(latest);
  return (
    <Widget title="Decision calendar" subtitle="Trade decisions, passes, safety blocks, and closed P&L by UTC day" className={className}>
      <MiniCalendar entries={calendar} month={month} onMonth={setMonth} onDay={onDay} expanded={expanded} selected={selected} />
    </Widget>
  );
}

function Overview({ overview, analytics, calendar, decisions, status, openDecision, setPage }) {
  const hasClosed = Number(overview?.closed_trades ?? 0) > 0;
  const closedMetric = (value, options) => hasClosed ? money(value, options) : "—";
  return (
    <div className="fade-in grid grid-cols-1 gap-3 lg:grid-cols-4">
      <AccountWidget status={status} />
      <MetricCard label="Realized net" value={closedMetric(overview?.realized_pnl)} detail={hasClosed ? `${overview.closed_trades} broker-joined closes` : "No closed sample"} icon={CircleDollarSign} tone={hasClosed ? toneFor(overview?.realized_pnl) : "text-bright"} />
      <MetricCard label="Win rate" value={percent(overview?.win_rate)} detail={overview?.closed_trades ? `${overview.wins} wins · ${overview.losses} losses` : "No closed sample"} icon={Target} />
      <MetricCard label="Profit factor" value={number(overview?.profit_factor)} detail="Gross wins ÷ gross losses" icon={Gauge} tone={overview?.profit_factor == null ? "text-bright" : Number(overview.profit_factor) >= 1 ? "text-positive" : "text-negative"} />
      <MetricCard label="Average R" value={overview?.average_r == null ? "—" : `${number(overview.average_r)} R`} detail="Net outcome ÷ stored entry risk" icon={ShieldCheck} tone={toneFor(overview?.average_r)} />
      <MetricCard label="Max drawdown" value={closedMetric(analytics?.maxDrawdown, { signed: false })} detail={hasClosed ? "Peak-to-trough realized lab P&L" : "No closed sample"} icon={TrendingDown} tone={hasClosed && analytics?.maxDrawdown ? "text-negative" : "text-bright"} />
      <MetricCard label="Decisions" value={overview?.decisions ?? "—"} detail={`${overview?.gated ?? 0} blocked · ${overview?.no_trades ?? 0} passed`} icon={Bot} />
      <EquityWidget analytics={analytics} />
      <CalendarWidget calendar={calendar} className="lg:col-span-2" onDay={() => setPage("calendar")} />
      <DecisionMix analytics={analytics} />
      <Widget title="Risk & costs" subtitle="Exact joined broker values">
        <div className="divide-y divide-line">
          {[
            ["Expectancy / trade", closedMetric(overview?.expectancy), toneFor(overview?.expectancy)],
            ["Best trade", closedMetric(overview?.best_trade), toneFor(overview?.best_trade)],
            ["Worst trade", closedMetric(overview?.worst_trade), toneFor(overview?.worst_trade)],
            ["Commission total", closedMetric(overview?.commission), overview?.commission ? "text-negative" : "text-bright"],
            ["Swap total", closedMetric(overview?.swap), toneFor(overview?.swap)],
          ].map(([label, value, tone]) => (
            <div key={label} className="flex items-center justify-between px-4 py-3 text-xs">
              <span className="text-muted">{label}</span>
              <strong className={`mono ${hasClosed ? tone : "text-bright"}`}>{value}</strong>
            </div>
          ))}
        </div>
      </Widget>
      <Widget
        title="Recent decisions"
        subtitle="Latest model decisions and deterministic gates"
        action={<button type="button" onClick={() => setPage("journal")} className="flex h-10 items-center gap-1 px-1 text-[11px] font-semibold text-accent hover:text-bright">View journal <ArrowRight size={12} aria-hidden="true" /></button>}
        className="lg:col-span-4"
      >
        <DecisionTable rows={decisions.slice(0, 8)} onOpen={openDecision} compact />
      </Widget>
    </div>
  );
}

function JournalPage({ decisions, allDecisions, openDecision, action, setAction, search, setSearch }) {
  const filters = [
    ["", "All", allDecisions.length],
    ["TRADE", "Trades", allDecisions.filter((row) => row.action === "TRADE").length],
    ["NO_TRADE", "Passed", allDecisions.filter((row) => row.action === "NO_TRADE").length],
    ["GATED", "Blocked", allDecisions.filter((row) => row.action === "GATED").length],
  ];
  return (
    <div className="fade-in">
      <Widget
        title="All recorded decisions"
        subtitle="Broker-truth audit log · newest first · UTC"
        action={<span role="status" aria-live="polite" className="mono text-[10px] text-muted">{decisions.length} result{decisions.length === 1 ? "" : "s"}</span>}
      >
        <div className="flex flex-wrap gap-2 border-b border-line p-3">
          <div className="flex min-w-[240px] flex-1 items-center gap-2 rounded-lg border border-line-strong bg-ink px-3 text-muted focus-within:border-accent">
            <label htmlFor="decision-search" className="sr-only">Search decisions</label>
            <Search size={14} aria-hidden="true" />
            <input id="decision-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search decisions, explanations, or instrument…" className="h-10 w-full bg-transparent text-xs text-body outline-none placeholder:text-faint" />
            {search && (
              <button type="button" onClick={() => setSearch("")} aria-label="Clear decision search" className="grid h-8 w-8 shrink-0 place-items-center rounded-md text-muted hover:bg-raised hover:text-bright">
                <X size={13} aria-hidden="true" />
              </button>
            )}
          </div>
          <div className="flex max-w-full overflow-auto rounded-lg border border-line-strong bg-ink p-1" role="group" aria-label="Filter journal by outcome">
            {filters.map(([value, label, count]) => (
              <button
                key={label}
                type="button"
                aria-pressed={action === value}
                onClick={() => setAction(value)}
                className={`flex h-10 shrink-0 items-center gap-1.5 rounded-md px-3 text-[11px] font-semibold transition ${action === value ? "bg-raised text-bright shadow-sm" : "text-muted hover:text-body"}`}
              >
                {label}<span className={`mono text-[10px] ${action === value ? "text-accent" : "text-faint"}`}>{count}</span>
              </button>
            ))}
          </div>
        </div>
        <DecisionTable rows={decisions} onOpen={openDecision} />
      </Widget>
    </div>
  );
}

function CalendarPage({ calendar, decisions, openDecision }) {
  const [selected, setSelected] = useState(() => calendar.at(-1)?.date ?? null);
  useEffect(() => {
    if (!selected && calendar.length) setSelected(calendar.at(-1).date);
  }, [calendar, selected]);
  const selectedRows = selected
    ? decisions.filter((row) => String(row.ts).startsWith(selected))
    : [];
  const day = calendar.find((item) => item.date === selected);
  const selectedLabel = selected ? utc(`${selected}T00:00:00Z`, { dateOnly: true }) : "";
  return (
    <div className="fade-in grid items-start gap-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(360px,.6fr)]">
      <CalendarWidget calendar={calendar} expanded onDay={setSelected} selected={selected} />
      <div className="min-w-0">
        <span className="sr-only" role="status" aria-live="polite">{selected ? `${selectedLabel} selected; ${selectedRows.length} decisions` : "No trading day selected"}</span>
      <Widget title={selectedLabel || "Day review"} subtitle={selected ? "Decisions recorded on this UTC day" : "Select a populated day"}>
        {selected ? (
          <>
            <div className="grid grid-cols-2 border-b border-line sm:grid-cols-4">
              {[
                ["Decisions", day?.decisions ?? selectedRows.length],
                ["Trades", day?.trade_decisions ?? selectedRows.filter((row) => row.action === "TRADE").length],
                ["Passed", day?.no_trades ?? selectedRows.filter((row) => row.action === "NO_TRADE").length],
                ["Blocked", day?.gated ?? selectedRows.filter((row) => row.action === "GATED").length],
              ].map(([label, value]) => (
                <div key={label} className="border-r border-line px-3 py-3 last:border-r-0">
                  <span className="eyebrow">{label}</span>
                  <strong className="mono mt-1 block text-sm text-bright">{value}</strong>
                </div>
              ))}
            </div>
            <DecisionTable rows={selectedRows} onOpen={openDecision} compact cardView />
          </>
        ) : <EmptyState icon={CalendarDays} title="Choose a day" copy="Select a recorded day to inspect every execution, pass, and safety block." />}
      </Widget>
      </div>
    </div>
  );
}

function AnalyticsPage({ overview, analytics }) {
  const hourly = analytics?.hours ?? [];
  const setups = analytics?.setups ?? [];
  return (
    <div className="fade-in grid grid-cols-1 gap-3 lg:grid-cols-4">
      <MetricCard label="Closed sample" value={overview?.closed_trades ?? 0} detail="Only broker-joined outcomes" icon={Database} />
      <MetricCard label="Expectancy" value={money(overview?.expectancy)} detail="Mean net per closed trade" icon={TrendingUp} tone={toneFor(overview?.expectancy)} />
      <MetricCard label="Average R" value={overview?.average_r == null ? "—" : `${number(overview.average_r)} R`} detail="Risk-normalized performance" icon={ShieldCheck} tone={toneFor(overview?.average_r)} />
      <MetricCard label="Max drawdown" value={money(analytics?.maxDrawdown, { signed: false })} detail="Realized lab curve · USD" icon={TrendingDown} tone={analytics?.maxDrawdown ? "text-negative" : "text-bright"} />
      <Widget title="Performance by decision hour" subtitle="Entry decision time · UTC · net outcome" className="lg:col-span-2">
        {!hourly.length ? <EmptyState icon={Clock3} title="No hourly sample" copy="This breakdown appears after real trades close." /> : (
          <div className="h-72 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hourly} accessibilityLayer role="img" aria-label={`Net profit and loss by decision hour: ${hourly.map((item) => `${String(item.hour).padStart(2, "0")}:00, ${money(item.netPnl)}`).join("; ")}`}>
                <CartesianGrid stroke="#22272d" vertical={false} />
                <XAxis dataKey="hour" tickFormatter={(v) => `${String(v).padStart(2, "0")}:00`} stroke="#4e565f" tick={{ fontSize: 10 }} />
                <YAxis stroke="#4e565f" tick={{ fontSize: 10 }} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="netPnl" name="Net P&L" radius={[4, 4, 0, 0]}>
                  {hourly.map((item) => <Cell key={item.hour} fill={item.netPnl >= 0 ? "#3fe08c" : "#ff6b6b"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Widget>
      <DecisionMix analytics={analytics} />
      <Widget title="Sample integrity" subtitle="Why missing data stays visibly missing">
        <div className="space-y-3 p-4 text-xs leading-5 text-muted">
          <p><b className="text-bright">Currency:</b> USD net after commission and swap.</p>
          <p><b className="text-bright">R:</b> broker net divided by risk stored from actual fill.</p>
          <p><b className="text-bright">Curve:</b> cumulative lab P&L from zero—not broker balance.</p>
          <p><b className="text-bright">Empty widgets:</b> never replaced with fake zero-performance claims.</p>
        </div>
      </Widget>
      <Widget title="Setup leaderboard" subtitle="Outcomes grouped by the model's recorded setup" className="lg:col-span-4">
        {!setups.length ? <EmptyState icon={Target} title="No setup outcomes yet" copy="Setups are ranked only after their accepted broker trades close." /> : (
          <div className="overflow-auto">
            <table className="w-full min-w-[650px] text-left text-xs">
              <caption className="sr-only">Closed trade performance grouped by recorded setup</caption>
              <thead className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
                <tr><th scope="col" className="px-4 py-3">Setup</th><th scope="col" className="px-3 py-3">Trades</th><th scope="col" className="px-3 py-3">Win rate</th><th scope="col" className="px-3 py-3">Average R</th><th scope="col" className="px-4 py-3 text-right">Net P&L</th></tr>
              </thead>
              <tbody>{setups.map((row) => (
                <tr key={row.setup} className="border-b border-line/70">
                  <td className="px-4 py-3 font-medium text-bright">{row.setup}</td>
                  <td className="mono px-3 py-3">{row.trades}</td>
                  <td className="mono px-3 py-3">{percent(row.winRate)}</td>
                  <td className="mono px-3 py-3">{number(row.averageR)} R</td>
                  <td className={`mono px-4 py-3 text-right font-semibold ${toneFor(row.netPnl)}`}>{money(row.netPnl)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Widget>
    </div>
  );
}

function ServiceCard({ icon: Icon, title, state, value, detail }) {
  const iconTone = state === "ready" ? "text-positive" : state === "warn" ? "text-warning" : state === "down" ? "text-negative" : "text-muted";
  return (
    <article className="panel p-4" aria-label={`${title}: ${value}`}>
      <div className="flex items-start justify-between">
        <div className={`grid h-9 w-9 place-items-center rounded-lg border border-line bg-raised ${iconTone}`}><Icon size={17} aria-hidden="true" /></div>
        <StatusDot state={state} />
      </div>
      <h3 className="mt-4 text-sm font-semibold text-bright">{title}</h3>
      <p className="mono mt-1 text-xs text-body">{value}</p>
      <p className="mt-2 text-[10px] leading-4 text-faint">{detail}</p>
    </article>
  );
}

function SystemPage({ status, openDecision }) {
  const gatewayReady = status?.gateway?.online && status?.gateway?.http === 200;
  const accountReady = status?.account?.online && status?.account?.http === 200;
  const operations = status?.operations;
  const cycleHealth = operations?.cycleHealth ?? "waiting";
  const cycleReady = cycleHealth === "healthy";
  const cycleState = cycleReady ? "ready" : cycleHealth === "waiting" ? "idle" : "warn";
  const activity = operations?.activity24h ?? {};
  const lifecycle = operations?.lifecycle ?? {};
  const runByJob = new Map((operations?.jobRuns ?? []).map((run) => [run.job, run]));
  const latest = operations?.latestDecision;
  return (
    <div className="fade-in grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
      <Widget
        title="Decision loop"
        subtitle="Health is based on recorded work—not whether a container exists"
        className="md:col-span-2 xl:col-span-4"
        action={<span className={`flex items-center gap-2 text-[10px] font-semibold ${cycleReady ? "text-positive" : cycleHealth === "waiting" ? "text-muted" : "text-warning"}`}><StatusDot state={cycleState} />{titleCase(cycleHealth)}</span>}
      >
        <div className="grid gap-0 lg:grid-cols-[1.25fr_.75fr]">
          <div className="border-b border-line p-5 lg:border-b-0 lg:border-r">
            <div className="flex items-start gap-3">
              <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl border ${cycleReady ? "border-positive/25 bg-positive/10 text-positive" : "border-warning/25 bg-warning/10 text-warning"}`}>
                <Radio size={19} />
              </div>
              <div>
                <p className="eyebrow">Latest cycle</p>
                <h3 className="mt-1 text-lg font-semibold text-bright">
                  {latest ? decisionHeadline(latest) : "Waiting for the first decision cycle"}
                </h3>
                <p className="mt-2 max-w-2xl text-xs leading-5 text-muted">
                  {latest ? `${utc(latest.ts)} UTC · ${ageLabel(operations?.cycleAgeSeconds)}` : operations?.healthBasis}
                </p>
              </div>
            </div>
            {latest && (
              <button type="button" onClick={() => openDecision(latest.id)} className="mt-3 inline-flex h-10 items-center gap-1.5 text-[11px] font-semibold text-accent hover:text-bright">
                Review decision {latest.id}<ArrowRight size={13} aria-hidden="true" />
              </button>
            )}
          </div>
          <div className="grid grid-cols-2">
            {[
              ["Decisions · 24h", activity.decisions_24h ?? 0],
              ["Trade decisions", activity.trades_24h ?? 0],
              ["Passed", activity.no_trades_24h ?? 0],
              ["Blocked", activity.gated_24h ?? 0],
            ].map(([label, value]) => (
              <div key={label} className="border-b border-r border-line p-4 even:border-r-0">
                <span className="eyebrow">{label}</span>
                <strong className="mono mt-2 block text-xl text-bright">{value}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 border-t border-line px-5 py-3 text-[11px] text-muted">
          <span><b className="mono text-bright">{lifecycle.open_trades ?? 0}</b> open trades</span>
          <span><b className="mono text-bright">{lifecycle.closed_trades ?? 0}</b> closed outcomes</span>
          <span><b className="mono text-bright">{lifecycle.venue_rejects ?? 0}</b> venue rejects</span>
          <span className={status?.killSwitch ? "text-warning" : "text-positive"}>{status?.killSwitch ? "KILL engaged · new orders blocked" : "Order gate armed"}</span>
        </div>
      </Widget>

      <Widget title="Scheduled work" subtitle="Configured cadence and the last recorded result" className="md:col-span-2 xl:col-span-4">
        <div className="overflow-auto">
          <table className="w-full min-w-[760px] text-left text-xs">
            <caption className="sr-only">Configured scheduler jobs and their latest recorded result</caption>
            <thead className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
              <tr><th scope="col" className="px-4 py-3">Job</th><th scope="col" className="px-3 py-3">Purpose</th><th scope="col" className="px-3 py-3">Schedule · UTC</th><th scope="col" className="px-4 py-3">Last run</th></tr>
            </thead>
            <tbody>
              {(operations?.schedules ?? []).map((job) => {
                const run = runByJob.get(job.job);
                const running = run && !run.finished_at;
                const label = !run ? "Not recorded yet" : running ? "Running" : run.ok ? "Succeeded" : "Failed";
                const tone = !run ? "text-faint" : running ? "text-info" : run.ok ? "text-positive" : "text-negative";
                const RunIcon = !run ? Clock3 : running ? RefreshCw : run.ok ? CheckCircle2 : AlertTriangle;
                return (
                  <tr key={`${job.job}-${job.label}`} className="border-b border-line/70 align-top">
                    <td className="px-4 py-3 font-semibold text-bright">{job.label}</td>
                    <td className="max-w-xl px-3 py-3 leading-5 text-muted">{job.purpose}</td>
                    <td className="mono whitespace-nowrap px-3 py-3 text-[10px] text-body">{job.schedule}</td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className={`flex items-center gap-1.5 font-semibold ${tone}`}><RunIcon size={13} aria-hidden="true" className={running ? "animate-spin" : ""} />{label}</span>
                      {run && <time dateTime={run.started_at} className="mono mt-1 block text-[10px] text-faint">{utc(run.started_at)} UTC</time>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Widget>

      <ServiceCard icon={Server} title="MT5 gateway" state={gatewayReady ? "ready" : "down"} value={gatewayReady ? "READY" : `HTTP ${status?.gateway?.http ?? "offline"}`} detail="Authenticated readiness probe; the public root intentionally returns Unauthorized." />
      <ServiceCard icon={CircleDollarSign} title="Broker account" state={accountReady ? "ready" : "down"} value={status?.account?.body?.server ?? "Unavailable"} detail={accountReady ? "Authenticated Exness account truth." : "Balance and execution truth are unavailable."} />
      <ServiceCard icon={Database} title="Journal database" state="ready" value="CONNECTED" detail="One source of truth for decisions, outcomes, analytics, and operational runs." />
      <ServiceCard icon={ShieldCheck} title="Order gate" state={status?.killSwitch ? "warn" : "ready"} value={status?.killSwitch ? "KILL ENGAGED" : "ARMED"} detail={status?.killSwitch ? "All new orders are refused." : "Other deterministic gates still apply."} />
      <Widget title="Evidence contract" subtitle="What this journal can honestly claim" className="md:col-span-2">
        <dl className="grid grid-cols-1 sm:grid-cols-2">
          {[
            ["Price source", "Exness MT5 via qkt"],
            ["Time basis", "UTC everywhere"],
            ["Decision evidence", "Archived before proposal"],
            ["Performance", "Broker-joined net only"],
            ["Missing values", "Shown as unavailable"],
            ["Order access", "None from this UI"],
          ].map(([term, detail]) => (
            <div key={term} className="border-b border-line px-4 py-3 odd:sm:border-r">
              <dt className="eyebrow">{term}</dt><dd className="mono mt-1.5 text-[11px] text-bright">{detail}</dd>
            </div>
          ))}
        </dl>
      </Widget>
      <Widget title="Execution boundary" subtitle="Current management semantics" className="md:col-span-2">
        <div className="grid gap-3 p-4 sm:grid-cols-2">
          {[
            [Check, "Automatic", "Market entry with broker-held SL and TP; 15-minute close join."],
            [X, "Not automatic", "Written invalidation, trailing, break-even, time exit, and partial close."],
            [Zap, "Before Codex", "Quote freshness/integrity and venue availability."],
            [Bot, "After Codex", "Sizing, RR, direction, exposure, daily loss, news, and KILL gates."],
          ].map(([Icon, label, copy]) => (
            <div key={label} className="rounded-xl border border-line bg-ink p-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-bright"><Icon size={14} className="text-accent" />{label}</div>
              <p className="mt-2 text-[10px] leading-4 text-muted">{copy}</p>
            </div>
          ))}
        </div>
      </Widget>
    </div>
  );
}

function TradingViewEvidence({ snapshotUrl }) {
  const hostRef = useRef(null);
  const chartRef = useRef(null);
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setSnapshot(null);
    setError("");
    getJson(snapshotUrl).then((data) => {
      if (!cancelled) setSnapshot(data);
    }).catch((err) => {
      if (!cancelled) setError(err instanceof Error ? err.message : String(err));
    });
    return () => { cancelled = true; };
  }, [snapshotUrl]);

  useEffect(() => {
    if (!snapshot || !hostRef.current) return undefined;
    const host = hostRef.current;
    const compact = host.clientWidth < 640;
    const chartHeight = compact ? 520 : 620;
    const chart = createChart(host, {
      width: host.clientWidth,
      height: chartHeight,
      layout: { background: { type: ColorType.Solid, color: "#090b0d" }, textColor: "#7b848e", fontFamily: "ui-monospace, monospace" },
      grid: { vertLines: { color: "#171b1f" }, horzLines: { color: "#24292f" } },
      rightPriceScale: { borderColor: "#343b43" },
      timeScale: { borderColor: "#343b43", timeVisible: true, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });
    chartRef.current = chart;
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#3fe08c", downColor: "#ff6b6b", borderVisible: false,
      wickUpColor: "#3fe08c", wickDownColor: "#ff6b6b",
    });
    candles.setData(snapshot.bars);
    const ema = chart.addSeries(LineSeries, { color: "#c8f74a", lineWidth: 2, title: "EMA 50", priceLineVisible: false });
    ema.setData(snapshot.studies.ema50);
    const rsi = chart.addSeries(LineSeries, {
      color: "#a78bfa", lineWidth: 2, title: "RSI 14", priceLineVisible: false,
      priceFormat: { type: "price", precision: 1, minMove: 0.1 },
    }, 1);
    rsi.setData(snapshot.studies.rsi14);
    [30, 70].forEach((price) => rsi.createPriceLine({
      price, color: "#3b424a", lineWidth: 1, lineStyle: LineStyle.Dashed,
      axisLabelVisible: true, title: `RSI ${price}`,
    }));
    const atr = chart.addSeries(LineSeries, {
      color: "#5cb8ff", lineWidth: 2, title: "ATR 14", priceLineVisible: false,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    }, 2);
    atr.setData(snapshot.studies.atr14);
    const panes = chart.panes();
    if (panes.length >= 3) {
      panes[0].setHeight(compact ? 320 : 380);
      panes[1].setHeight(compact ? 90 : 110);
      panes[2].setHeight(compact ? 90 : 110);
    }
    chart.timeScale().fitContent();
    const observer = new ResizeObserver(() => chart.applyOptions({ width: host.clientWidth }));
    observer.observe(host);
    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [snapshot]);

  const save = () => {
    const canvas = chartRef.current?.takeScreenshot(true, true);
    if (!canvas) return;
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = `${snapshot?.title?.replaceAll(/[^a-z0-9_-]+/gi, "-") || "qkt-chart"}.png`;
    link.click();
  };

  const lastBar = snapshot?.bars?.at(-1);
  const lastStudy = (name) => snapshot?.studies?.[name]?.at(-1)?.value;
  const chartDescription = snapshot
    ? `${snapshot.title}. ${snapshot.barCount} broker bars in ${snapshot.timezone}. Latest close ${number(lastBar?.close, 2)}, EMA 50 ${number(lastStudy("ema50"), 2)}, RSI 14 ${number(lastStudy("rsi14"), 1)}, ATR 14 ${number(lastStudy("atr14"), 2)}.`
    : "Loading archived broker chart.";
  if (error) return <EmptyState icon={BarChart3} title="Interactive chart unavailable" copy="The stored chart data could not be rendered. The original archived PNG remains available below." />;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <strong className="text-xs text-bright">{snapshot?.title ?? "Loading broker snapshot…"}</strong>
          <p className="mt-1 text-[10px] text-faint">{snapshot ? `${snapshot.source} · ${snapshot.timezone} · ${snapshot.barCount} bars` : "Loading exact archived data"}</p>
        </div>
        <button type="button" disabled={!snapshot} onClick={save} className="flex h-10 items-center gap-2 rounded-lg border border-line-strong bg-raised px-3 text-[11px] font-semibold text-accent hover:border-accent disabled:cursor-not-allowed disabled:opacity-40">
          <Download size={13} aria-hidden="true" /> Save chart PNG
        </button>
      </div>
      <p id="chart-description" className="sr-only">{chartDescription}</p>
      {!snapshot && <div role="status" className="flex min-h-48 items-center justify-center gap-2 text-xs text-muted"><RefreshCw size={14} className="animate-spin" aria-hidden="true" />Loading archived chart data</div>}
      <div
        ref={hostRef}
        role="group"
        aria-label="Interactive archived broker chart"
        aria-describedby="chart-description"
        className={`${snapshot ? "min-h-[520px] md:min-h-[620px]" : "h-0"} w-full`}
      />
    </div>
  );
}

function DetailSection({ title, icon: Icon, children, className = "" }) {
  return (
    <section className={`rounded-xl border border-line bg-ink p-4 md:p-5 ${className}`}>
      <h3 className="flex items-center gap-2 text-xs font-semibold text-bright">
        {Icon && <Icon size={14} className="text-accent" />}{title}
      </h3>
      <div className="mt-3 text-[13px] leading-6 text-body">{children || <span className="text-faint">Not recorded.</span>}</div>
    </section>
  );
}

function DecisionDetail({ id, close }) {
  const [row, setRow] = useState(null);
  const [chartIndex, setChartIndex] = useState(0);
  const [loadError, setLoadError] = useState("");
  const [retryKey, setRetryKey] = useState(0);
  const dialogRef = useRef(null);
  const titleRef = useRef(null);
  const returnFocusRef = useRef(document.activeElement);
  useEffect(() => {
    setRow(null);
    setChartIndex(0);
    setLoadError("");
    getJson(`/api/decisions/${id}`).then(setRow).catch(() => {
      setLoadError("The journal entry could not be loaded.");
    });
  }, [id, retryKey]);
  useEffect(() => {
    const shell = document.getElementById("app-shell");
    const previousOverflow = document.body.style.overflow;
    shell?.setAttribute("inert", "");
    shell?.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => titleRef.current?.focus());
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = [...dialogRef.current.querySelectorAll(
        'button:not([disabled]), a[href], summary, [tabindex]:not([tabindex="-1"])',
      )].filter((element) => !element.hasAttribute("hidden"));
      if (!focusable.length) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!focusable.includes(document.activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      shell?.removeAttribute("inert");
      shell?.removeAttribute("aria-hidden");
      document.body.style.overflow = previousOverflow;
      returnFocusRef.current?.focus?.();
    };
  }, [close]);
  const chart = row?.chartViews?.[chartIndex];
  const context = row?.context_snapshot ?? {};
  const marketState = marketStateFor(row);
  const events = Array.isArray(row?.news) ? row.news : [];
  const isPreflightGate = row?.action === "GATED" && context.stage === "venue_preflight";
  return (
    <div
      ref={dialogRef}
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="decision-detail-title"
      aria-busy={!row && !loadError}
    >
      <div className="absolute inset-y-0 right-0 w-full overscroll-contain overflow-auto border-l border-line bg-panel shadow-2xl xl:w-[min(1180px,92vw)]">
        <div className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-line bg-panel/95 px-4 py-3 backdrop-blur md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button type="button" aria-label="Close decision review" onClick={close} className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-line-strong bg-raised text-muted hover:border-accent hover:text-bright"><ArrowLeft size={17} aria-hidden="true" /></button>
            <div className="min-w-0">
              <span className="eyebrow">{row ? `Decision ${row.id}` : "Loading decision"}</span>
              <h2 id="decision-detail-title" ref={titleRef} tabIndex={-1} className="mt-1 truncate text-base font-semibold text-bright">{row ? row.symbol : "Decision review"}</h2>
            </div>
          </div>
          {row && <ActionPill action={row.action} accepted={row.accepted} />}
        </div>
        {loadError ? (
          <div className="grid min-h-[60vh] place-items-center px-6 text-center">
            <div>
              <AlertTriangle className="mx-auto text-warning" aria-hidden="true" />
              <p role="alert" className="mt-3 text-sm font-semibold text-bright">{loadError}</p>
              <button type="button" onClick={() => setRetryKey((value) => value + 1)} className="mt-4 h-10 rounded-lg border border-line-strong bg-raised px-4 text-xs font-semibold text-accent hover:border-accent">Try again</button>
            </div>
          </div>
        ) : !row ? <div role="status" className="grid min-h-[60vh] place-items-center"><span className="flex items-center gap-2 text-xs text-muted"><RefreshCw className="animate-spin text-accent" aria-hidden="true" />Loading decision evidence</span></div> : (
          <div className="space-y-3 p-3 md:p-6">
            <section className={`overflow-hidden rounded-2xl border ${row.action === "GATED" ? "border-warning/25 bg-warning/5" : row.accepted ? "border-positive/25 bg-positive/5" : "border-line bg-raised/40"}`}>
              <div className="p-5 md:p-6">
                <div className="flex flex-wrap items-center gap-2">
                  <ActionPill action={row.action} accepted={row.accepted} />
                  <span className="mono text-[10px] text-faint">{row.symbol?.split(":").at(-1)} · UTC</span>
                </div>
                <h2 className="mt-4 max-w-4xl text-xl font-semibold tracking-[-.02em] text-bright md:text-2xl">{decisionHeadline(row)}</h2>
                <p className="mt-3 max-w-4xl text-sm leading-6 text-body">{decisionSummary(row)}</p>
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-2 border-t border-line/80 px-5 py-3 text-[11px] text-muted md:px-6">
                <span>Setup <b className="ml-1 text-body">{titleCase(row.setup || "Unclassified")}</b></span>
                <span>Confidence <b className="mono ml-1 text-body">{row.conviction == null ? "Not scored" : percent(Number(row.conviction) * 100)}</b></span>
                <span>Recorded <b className="mono ml-1 text-body">{utc(row.ts)} UTC</b></span>
              </div>
            </section>

            {row.accepted ? (
              <div className="grid grid-cols-2 gap-2 lg:grid-cols-6">
                <MetricCard label="Side" value={row.side || "—"} detail={row.lots == null ? "No order" : `${number(row.lots)} lots`} icon={row.side === "SELL" ? ArrowDownRight : ArrowUpRight} tone={row.side === "SELL" ? "text-violet" : "text-info"} />
                <MetricCard label="Fill" value={row.fill_price == null ? "—" : number(row.fill_price, 3)} detail={row.ticket ? `ticket ${row.ticket}` : "No broker ticket"} icon={Zap} />
                <MetricCard label="Stop" value={row.sl == null ? "—" : number(row.sl, 3)} detail={row.risk_at_entry == null ? "Risk unavailable" : `${money(row.risk_at_entry, { signed: false })} at entry`} icon={ShieldCheck} />
                <MetricCard label="Target" value={row.tp == null ? "—" : number(row.tp, 3)} detail={row.expected_rr == null ? "No RR claim" : `${number(row.expected_rr)} planned RR`} icon={Target} />
                <MetricCard label="Net result" value={row.net_pnl == null ? "OPEN" : money(row.net_pnl)} detail={row.r_multiple == null ? "R pending" : `${number(row.r_multiple)} R`} icon={CircleDollarSign} tone={toneFor(row.net_pnl)} />
                <MetricCard label="Duration" value={duration(row.duration_s)} detail={row.closed_at ? `closed ${utc(row.closed_at)}` : "Position remains open"} icon={Clock3} />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
                {[
                  [CircleSlash2, "Position", "None opened", row.action === "GATED" ? "Stopped by a safety check" : "The analyst chose to pass"],
                  [Gauge, "Confidence", row.conviction == null ? "Not scored" : percent(Number(row.conviction) * 100), "Confidence in the recorded decision"],
                  [TimerReset, "Market data", isPreflightGate ? "Rejected" : row.factors?.some((item) => item.startsWith("data:")) ? "Questionable" : "Reviewed", isPreflightGate ? "Analysis stopped before model review" : "State at the decision timestamp"],
                  [ShieldCheck, "Capital at risk", money(0, { signed: false }), "No exposure was committed"],
                ].map(([Icon, label, value, detail]) => <MetricCard key={label} label={label} value={value} detail={detail} icon={Icon} />)}
              </div>
            )}

            <div className="grid gap-3 lg:grid-cols-2">
              <DetailSection title="Why this decision" icon={Compass} className="lg:col-span-2">
                {row.thesis ? <p className="whitespace-pre-wrap">{row.thesis}</p> : (
                  <p className="text-muted">{isPreflightGate ? "The safety layer stopped the cycle before the analyst was given market context." : decisionSummary(row)}</p>
                )}
                {row.rationale_md && row.rationale_md !== row.thesis && (
                  <div className="mt-4 border-t border-line pt-4">
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-[.12em] text-muted">Analyst review</p>
                    <p className="whitespace-pre-wrap">{row.rationale_md}</p>
                  </div>
                )}
              </DetailSection>

              <DetailSection title="What the system observed" icon={Layers3}>
                {row.factors?.length ? (
                  <div className="space-y-2">
                    {row.factors.map((item) => {
                      const factor = humanFactor(item);
                      const FactorIcon = factorIcon(item);
                      return (
                        <div key={item} className="rounded-lg border border-line bg-raised/45 p-3">
                          <div className="flex items-center justify-between gap-3">
                            <strong className="flex items-center gap-2 text-[11px] text-bright"><FactorIcon size={13} aria-hidden="true" className="text-accent" />{factor.label}</strong>
                            <span className="text-[10px] text-muted">{factor.value}</span>
                          </div>
                          <p className="mt-1.5 text-[11px] leading-5 text-muted">{factorExplanation(item)}</p>
                        </div>
                      );
                    })}
                  </div>
                ) : <p className="text-muted">{isPreflightGate ? "No technical observations were generated because the quote failed preflight." : "No structured observations were recorded."}</p>}
              </DetailSection>

              <DetailSection title="Market state & indicators" icon={Activity}>
                {marketState.length ? (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {marketState.map((item, index) => (
                      <div key={`${item.label}-${index}`} className="rounded-lg border border-line bg-raised/45 p-3">
                        <span className="text-[10px] text-muted">{titleCase(item.label)}</span>
                        <strong className="mono mt-1 block text-sm text-bright">{typeof item.value === "number" ? number(item.value) : titleCase(item.value)}</strong>
                        <p className="mt-1 text-[10px] leading-4 text-faint">
                          {String(item.label).toLowerCase().includes("atr") ? "Current price volatility over 14 bars."
                            : String(item.label).toLowerCase().includes("ema") ? "Moving-average baseline used for direction and location."
                              : String(item.label).toLowerCase().includes("rsi") ? "Momentum reading over 14 bars."
                                : "Market condition recorded at decision time."}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-muted">{isPreflightGate ? "Indicators were not calculated after the stale quote failed the venue check." : "No indicator values were stored for this historical decision."}</p>}
              </DetailSection>

              <DetailSection title="News & scheduled events" icon={Newspaper}>
                {events.length ? (
                  <div className="space-y-2">{events.map((event, index) => (
                    <article key={`${event.id || event.title || "event"}-${index}`} className="rounded-lg border border-line bg-raised/45 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <strong className="text-xs text-bright">{event.title || event.event || event.name || "Market event"}</strong>
                        {(event.time || event.ts || event.at) && <span className="mono text-[9px] text-faint">{utc(event.time || event.ts || event.at)} UTC</span>}
                      </div>
                      <p className="mt-1.5 text-[11px] leading-5 text-muted">{event.effect || event.impact || event.detail || "Recorded as relevant context for this decision."}</p>
                    </article>
                  ))}</div>
                ) : <p className="text-muted">No confirmed relevant event was supplied for this decision. This is not a claim that the wider calendar was empty.</p>}
                {row.sources_missing?.length > 0 && (
                  <p className="mt-3 rounded-lg border border-warning/20 bg-warning/5 p-3 text-[11px] text-warning">
                    Some context sources were unavailable: {row.sources_missing.map(titleCase).join(", ")}.
                  </p>
                )}
              </DetailSection>

              <DetailSection title="What would change the view" icon={Route}>
                {row.invalidation ? <p className="whitespace-pre-wrap">{row.invalidation}</p> : <p className="text-muted">{isPreflightGate ? "Obtain a fresh, live-session quote and rerun the complete analysis." : "No explicit reassessment trigger was recorded."}</p>}
              </DetailSection>
            </div>

            <DetailSection title="Safety checks" icon={row.gate_rejects?.length ? AlertTriangle : CheckCircle2}>
              {row.gate_rejects?.length ? (
                <div className="space-y-2">{row.gate_rejects.map((item) => (
                  <div key={`${item.gate}-${item.detail}`} className="rounded-lg border border-warning/25 bg-warning/5 p-3">
                    <strong className="text-[11px] text-warning">{titleCase(item.gate)}</strong>
                    <p className="mt-1 text-xs text-body">{item.detail}</p>
                  </div>
                ))}</div>
              ) : <p className="text-muted">{row.action === "NO_TRADE" ? "No deterministic safety check forced this pass; the analyst declined the setup on its merits." : "No deterministic safety check rejected this proposal."}</p>}
            </DetailSection>

            {row.chartViews?.length ? (
              <Widget
                title="Chart evidence"
                subtitle="Exact broker bars and studies visible when this decision was made"
                action={<div className="flex gap-1 rounded-lg border border-line-strong bg-ink p-1" role="group" aria-label="Chart timeframe">{row.chartViews.map((item, index) => <button key={item.snapshot} type="button" aria-pressed={chartIndex === index} onClick={() => setChartIndex(index)} className={`h-10 rounded-md px-3 text-[11px] font-semibold ${chartIndex === index ? "bg-accent text-ink" : "text-muted hover:text-body"}`}>{item.label.replace("XAUUSD-", "").toUpperCase()}</button>)}</div>}
              >
                {chart?.snapshotAvailable ? <TradingViewEvidence snapshotUrl={chart.snapshot} /> : (
                  <a href={chart?.image} target="_blank" rel="noreferrer" aria-label={`Open archived ${chart?.label} model-input chart at full size`}><img src={chart?.image} alt={`Archived ${chart?.label} model-input chart`} className="w-full" /></a>
                )}
                {chart?.image && (
                  <div className="border-t border-line bg-ink/40 p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold text-bright">Original model-input PNG</p>
                        <p className="mt-1 text-[10px] text-muted">The immutable chart image stored with the journal entry</p>
                      </div>
                      <a href={chart.image} target="_blank" rel="noreferrer" className="inline-flex min-h-10 shrink-0 items-center gap-1.5 text-[11px] font-semibold text-accent hover:text-bright">Open full size <ExternalLink size={12} aria-hidden="true" /></a>
                    </div>
                    <a href={chart.image} target="_blank" rel="noreferrer" aria-label={`Open original archived ${chart.label} PNG at full size`} className="block overflow-hidden rounded-xl border border-line bg-ink">
                      <img src={chart.image} alt={`Original archived ${chart.label} chart used as model input`} loading="lazy" className="max-h-[620px] w-full object-contain" />
                    </a>
                  </div>
                )}
              </Widget>
            ) : <Widget title="Chart evidence"><EmptyState icon={BarChart3} title="No chart was produced" copy={isPreflightGate ? "The quote failed a safety check before chart rendering and model analysis." : "This historical entry has no archived chart artifact."} /></Widget>}

            <details className="rounded-xl border border-line bg-ink">
              <summary className="flex cursor-pointer items-center gap-2 px-4 py-3 text-xs font-semibold text-muted hover:text-bright">
                <FileText size={14} />Technical audit trail
              </summary>
              <div className="grid gap-3 border-t border-line p-3 lg:grid-cols-2">
                <DetailSection title="Execution provenance">
                  <pre className="mono overflow-auto whitespace-pre-wrap text-[10px]">{JSON.stringify({
                    accepted: row.accepted, ticket: row.ticket, deal: row.open_deal,
                    retcode: row.retcode, broker_symbol: row.broker_symbol,
                    qkt_version: row.qkt_version, model: row.model, prompt_sha: row.prompt_sha,
                    arm: row.arm,
                  }, null, 2)}</pre>
                </DetailSection>
                <DetailSection title="Knowledge provenance">
                  <pre className="mono overflow-auto whitespace-pre-wrap text-[10px]">{JSON.stringify({
                    beliefs_used: row.beliefs_used, map_nodes_used: row.map_nodes_used,
                    sources_read: row.sources_read, procedures_used: row.procedures_used,
                    sources_missing: row.sources_missing, unexplained: row.unexplained,
                  }, null, 2)}</pre>
                </DetailSection>
              </div>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const initial = window.location.hash.replace("#", "");
  const [page, setPageState] = useState(Object.hasOwn(PAGE_COPY, initial) ? initial : "overview");
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("qkt-journal-sidebar") === "collapsed");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [overview, setOverview] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [calendar, setCalendar] = useState([]);
  const [status, setStatus] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [action, setAction] = useState("");
  const [search, setSearch] = useState("");
  const [detailId, setDetailId] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const pageHeadingRef = useRef(null);
  const menuButtonRef = useRef(null);
  const firstPageRender = useRef(true);

  const setPage = useCallback((next) => {
    const selected = Object.hasOwn(PAGE_COPY, next) ? next : "overview";
    setPageState(selected);
    window.history.pushState({ page: selected }, "", `#${selected}`);
    window.scrollTo({ top: 0, behavior: "auto" });
  }, []);

  const closeMobile = useCallback((restoreFocus = true) => {
    setMobileOpen(false);
    if (restoreFocus) requestAnimationFrame(() => menuButtonRef.current?.focus());
  }, []);

  const closeDecision = useCallback(() => setDetailId(null), []);

  useEffect(() => {
    localStorage.setItem("qkt-journal-sidebar", collapsed ? "collapsed" : "expanded");
  }, [collapsed]);

  useEffect(() => {
    const onHash = () => {
      const selected = window.location.hash.replace("#", "");
      setPageState(Object.hasOwn(PAGE_COPY, selected) ? selected : "overview");
    };
    window.addEventListener("popstate", onHash);
    window.addEventListener("hashchange", onHash);
    return () => {
      window.removeEventListener("popstate", onHash);
      window.removeEventListener("hashchange", onHash);
    };
  }, []);

  useEffect(() => {
    document.title = `${PAGE_COPY[page][1]} · qkt-lab`;
    if (firstPageRender.current) {
      firstPageRender.current = false;
      return;
    }
    requestAnimationFrame(() => pageHeadingRef.current?.focus());
  }, [page]);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [overviewData, analyticsData, calendarData, statusData, decisionData] = await Promise.all([
        getJson("/api/overview"),
        getJson("/api/analytics"),
        getJson("/api/calendar"),
        getJson("/api/status"),
        getJson("/api/decisions?limit=500"),
      ]);
      setOverview(overviewData);
      setAnalytics(analyticsData);
      setCalendar(calendarData);
      setStatus(statusData);
      setDecisions(decisionData);
      setLastUpdated(new Date());
      setError("");
    } catch (err) {
      setError(String(err));
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 15_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const filtered = useMemo(() => decisions.filter((row) => {
    if (action && row.action !== action) return false;
    const query = search.trim().toLowerCase();
    if (!query) return true;
    return [row.symbol, row.setup, row.thesis, row.rationale_md, row.side, row.action]
      .some((value) => String(value ?? "").toLowerCase().includes(query));
  }), [decisions, action, search]);

  const [eyebrow, title, description] = PAGE_COPY[page];
  const initialLoading = !overview && !status && refreshing && !error;
  const content = {
    overview: <Overview overview={overview} analytics={analytics} calendar={calendar} decisions={decisions} status={status} openDecision={setDetailId} setPage={setPage} />,
    journal: <JournalPage decisions={filtered} allDecisions={decisions} openDecision={setDetailId} action={action} setAction={setAction} search={search} setSearch={setSearch} />,
    calendar: <CalendarPage calendar={calendar} decisions={decisions} openDecision={setDetailId} />,
    analytics: <AnalyticsPage overview={overview} analytics={analytics} />,
    system: <SystemPage status={status} openDecision={setDetailId} />,
  }[page];

  return (
    <div className="min-h-screen">
      <div id="app-shell">
      <a href="#main-content" className="fixed left-3 top-3 z-[70] -translate-y-20 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-ink transition-transform focus:translate-y-0">Skip to main content</a>
      <div className="fixed inset-x-0 top-0 z-40 flex h-14 items-center gap-3 border-b border-line bg-panel px-3 md:hidden">
        <button
          ref={menuButtonRef}
          type="button"
          aria-label="Open navigation"
          aria-expanded={mobileOpen}
          aria-controls="primary-navigation"
          onClick={() => setMobileOpen(true)}
          className="grid h-10 w-10 place-items-center rounded-lg border border-line-strong bg-raised text-body"
        >
          <Menu size={18} aria-hidden="true" />
        </button>
        <QktMark className="h-7 w-7" />
        <strong className="text-sm text-bright">qkt<span className="text-accent">·</span>lab</strong>
        <span className="ml-auto flex items-center gap-2 text-[10px] font-semibold text-muted">
          <StatusDot state={status?.gateway?.http === 200 ? "ready" : "down"} />
          <span className="sr-only">{status?.gateway?.http === 200 ? "Gateway connected" : "Gateway unavailable"}</span>
        </span>
      </div>
      <Sidebar page={page} setPage={setPage} collapsed={collapsed} setCollapsed={setCollapsed} mobileOpen={mobileOpen} closeMobile={closeMobile} status={status} />
      <main id="main-content" tabIndex={-1} className={`min-w-0 px-3 pb-12 pt-[76px] transition-[margin] duration-200 sm:px-5 md:pt-7 ${collapsed ? "md:ml-[72px]" : "md:ml-[264px]"}`}>
        <div className="mx-auto w-full max-w-[1540px]">
          <header className="mb-5 flex items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="eyebrow">{eyebrow}</p>
              <h1 ref={pageHeadingRef} tabIndex={-1} className="mt-1 text-2xl font-bold tracking-[-.03em] text-bright sm:text-3xl">{title}</h1>
              <p className="mt-1 max-w-2xl text-xs leading-5 text-muted">{description}</p>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              {lastUpdated && <span className="hidden text-right text-[10px] leading-4 text-faint lg:block">Updated<br /><time dateTime={lastUpdated.toISOString()}>{new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(lastUpdated)}</time></span>}
              <button type="button" aria-label={refreshing ? "Refreshing journal data" : "Refresh journal data"} aria-busy={refreshing} onClick={load} disabled={refreshing} className="flex h-10 shrink-0 items-center gap-2 rounded-lg border border-line-strong bg-raised px-3 text-[11px] font-semibold text-body hover:border-accent hover:text-accent disabled:cursor-wait disabled:opacity-60">
                <RefreshCw size={13} aria-hidden="true" className={refreshing ? "animate-spin" : ""} />
                <span className="hidden sm:inline">{refreshing ? "Refreshing" : "Refresh"}</span>
              </button>
            </div>
          </header>
          {error && <div role="alert" className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-negative/30 bg-negative/5 px-4 py-3 text-xs text-negative"><span>Journal refresh failed. Existing data may be out of date.</span><button type="button" onClick={load} className="h-9 rounded-lg border border-negative/30 px-3 font-semibold hover:bg-negative/10">Try again</button></div>}
          {initialLoading ? (
            <div role="status" className="panel grid min-h-64 place-items-center"><span className="flex items-center gap-2 text-xs text-muted"><RefreshCw size={15} aria-hidden="true" className="animate-spin text-accent" />Loading broker and journal data</span></div>
          ) : content}
        </div>
      </main>
      </div>
      {detailId != null && <DecisionDetail id={detailId} close={closeDecision} />}
    </div>
  );
}
