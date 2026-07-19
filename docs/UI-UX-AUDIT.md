# Journal UI/UX pre-commit audit

Date: 2026-07-19

Scope: the first-party React journal at `http://localhost:8421`, including all
desktop and mobile layouts, keyboard interactions, status semantics, and every
reusable component in `journal-ui/src/App.jsx`.

## Decision standard

Every component is evaluated with the same questions:

1. **Trader task:** Does it help a trader understand account state, a decision,
   its evidence, its outcome, or system reliability?
2. **Visibility:** Is the current state and next available action obvious without
   remembering another screen?
3. **Integrity:** Does wording and color describe what the stored data actually
   proves, without implying execution, profit, or health that did not happen?
4. **Interaction:** Can pointer, keyboard, touch, and assistive-technology users
   operate it and recover from errors?
5. **Hierarchy:** Are related facts grouped, unrelated facts separated, and the
   most decision-relevant information encountered first?
6. **Visual semantics:** Does color, icon, sign, shape, and text carry one
   consistent meaning without relying on color alone?
7. **Responsive fit:** Does the component adapt to its container and task rather
   than merely shrinking its desktop layout?

The accessibility baseline is WCAG 2.2 AA. Interaction patterns follow the WAI
ARIA Authoring Practices where a native HTML element is insufficient.

## Semantic visual language

| Meaning | Encoding | Reason |
|---|---|---|
| Realized profit, successful job, healthy connection | green + signed value or success text/icon | Green means a genuinely favorable or healthy result. |
| Realized loss or failed/rejected operation | red + minus sign or failure text/icon | A loss/error is materially adverse and must not be color-only. |
| Trade decision or accepted execution | blue + lightning icon + label | Execution is activity, not proof of a win. |
| Buy / sell direction | blue / violet + `BUY` / `SELL` text and direction icon | Direction is not performance and should not borrow win/loss colors. |
| Deliberate pass | neutral gray + barred-circle icon + `Passed` | Passing is neither a failure nor a profit. |
| Safety block or KILL | amber + shield/warning icon + explicit text | It requires attention but is functioning as designed. |
| Selection/navigation | lime accent + border/fill + `aria-current`/`aria-pressed` | Brand selection is separate from market outcome colors. |
| Missing or insufficient evidence | em dash or explicit empty state | Zero is never substituted for unknown data. |

Up/down candles retain the familiar market-movement green/red convention, but
the chart has a textual description and numeric labels, so candle color is not
the only carrier of meaning.

## Component audit and resulting decisions

| Component | Trader/HCI assessment | Decision and implemented correction |
|---|---|---|
| Application shell | Persistent navigation is appropriate for repeated review, but SPA route changes originally did not announce location. | Keep the shell. Add a skip link, dynamic document titles, focus the new page heading, identify the active route with `aria-current`, and preserve reduced-motion behavior. |
| Desktop sidebar | Collapse supports dense chart review, but its old 24px control was hard to acquire and state dots could be unlabeled. | Use a larger high-contrast collapse target, persistent labels/tooltips, explicit gateway/KILL text, and non-color status meaning. |
| Mobile navigation | An off-canvas menu is appropriate, but visually translated content remained keyboard reachable. | Apply `inert` and `aria-hidden` while closed, expose `aria-expanded`/`aria-controls`, focus the current route when opened, and restore or advance focus when closed/navigated. |
| Page header and refresh | Page context and manual refresh are essential. An icon-only mobile refresh and unannounced error were ambiguous. | Give refresh an accessible name and busy state, show last-update time, use a 40px target, and present failures as an alert with retry while preserving existing data. |
| Widget container | Consistent card headers improve scanability; excessive decoration would compete with evidence. | Keep flat surfaces and restrained borders. Preserve one heading, optional subtitle, and one contextual action per widget. |
| Metric card | Compact KPIs suit a trading overview, but tiny low-contrast metadata and indiscriminate colors reduce trust. | Raise metadata contrast, keep missing values explicit, color only semantically meaningful values, and match the icon tone to that meaning. |
| Empty state | Necessary because a new lab legitimately has no closed sample. | Keep one short explanation of what evidence will populate the component; never render invented zeros or decorative charts. |
| Broker account | Balance, equity, margin, and open P&L belong together. | Keep one grouped account panel. Reserve green for authenticated connection and signed open P&L for performance; mask the login. |
| Realized P&L curve | A cumulative curve is the fastest view of performance trajectory, but green always implied profit. | Dynamically use green/red/neutral from the ending realized P&L, add a programmatic chart description, and retain an explicit no-sample state. |
| Decision mix | Useful for diagnosing selectivity, not profitability. | Encode trade decisions in blue, passes in neutral gray, and blocks in amber; accompany every slice with text and count. |
| Journal search | Search is necessary as the log grows; placeholder-only labeling was insufficient. | Add a programmatic label, native search input, visible clear action, high-contrast control boundary, and live result count. |
| Journal filters | Four mutually exclusive filters are faster as visible choices than a dropdown. | Keep a segmented button group with counts and `aria-pressed`; enlarge targets and allow horizontal overflow on narrow screens. |
| Decision table | Tabular comparison is right on wide screens, but clickable rows were mouse-only. | Preserve mouse row activation while adding a labeled 40px Review button per row, semantic caption/column headers/time elements, and focus-within state. |
| Mobile decision list | Cards are easier to scan than a compressed table. | Keep full-row buttons with outcome, instrument, headline, timestamp, and signed result. The accessible label announces the complete decision. |
| Calendar month control | Month context is useful, but unexplained dots and tiny arrow targets were not. | Use labeled 40px arrows, announce the month, remove all decorative dots, and make only recorded days interactive. |
| Calendar day cell | A day must communicate activity before selection. Absolute-positioned labels collided and compact counts truncated. | Use a flex layout with a stable date/header and bottom summary. Compact cells stack count and label; expanded cells show trade/pass/block/close text. Selection uses border, fill, and `aria-pressed`, not color alone. |
| Calendar day review | Day drill-down is core to journal use, but a 780px desktop table inside a narrow side panel required horizontal scrolling. | Use a container-appropriate decision-card list in the side panel and expose Decisions, Trades, Passed, and Blocked as a four-part summary. |
| Analytics KPI row | Sample size, expectancy, average R, and drawdown answer whether an edge is measurable. | Keep them together; use green/red only for signed expectancy/R and red for non-zero drawdown. Win rate remains neutral because it is not meaningful without payoff ratio. |
| Hour chart | Time-of-day performance is useful after closes. | Keep an honest empty state. When populated, retain signed bars and provide an accessible numeric description. |
| Setup leaderboard | A table is appropriate for comparing repeated setups. | Keep semantic headers/caption and signed net P&L. Do not rank setups before closed outcomes exist. |
| Decision loop status | The most important operational question is whether work was actually recorded. | Lead the System page with latest cycle, age, activity counts, lifecycle, KILL state, and direct review action. Health derives from the latest decision, not container decoration. |
| Scheduled work | Operators need cadence and last result without reading logs. | Keep a semantic table. Pair state colors with success/failure/running/waiting icons and text; show exact UTC timestamps and configured purpose. |
| Service cards | Useful secondary diagnostics, not the primary proof that the loop works. | Keep below recorded work, with icon, status text/value, and honest gateway-auth explanation. |
| Decision drawer | A drawer preserves list context and supports long evidence, but the original modal lacked a name, trap, focus restoration, and loading recovery. | Implement the WAI modal pattern: labeled dialog, background `inert`, initial title focus, Tab/Shift+Tab containment, Escape close, body-scroll lock, retry state, and focus restoration. |
| Decision summary | A seasoned trader needs outcome and reason before parameters. | Lead with outcome, plain-language thesis, setup, confidence, and recorded time. Show trade parameters only for accepted trades; passes/blocks show no-position and zero-exposure facts instead of meaningless dashes. |
| Observations | Raw factor tokens are auditable but poor review language. | Render categorized cards with meaningful icons and plain-language explanations for trend, entry, session, liquidity, data, event, spread, and level observations. |
| Market state | Indicators should answer what was observed, not expose JSON. | Deduplicate context/regime values; present named readings with short definitions. Keep raw values only in the audit disclosure. |
| News/events | Empty news must not imply the world calendar was empty. | State that no confirmed relevant event was supplied and separately disclose unavailable sources. |
| Invalidation | A review is incomplete without conditions that would change the view. | Keep it as a first-class trader section; for a preflight gate, explicitly require fresh data and a rerun. |
| Safety checks | Blocks must be distinguishable from analyst passes. | Show amber warning cards and gate names/details for forced blocks; explicitly say when a pass was discretionary. |
| Interactive chart | Exact decision-time market evidence is valuable, but canvas charts are difficult for assistive technology and fixed desktop height was poor on mobile. | Render exact archived bars/studies, use responsive pane heights, provide a full numeric text alternative, expose a labeled chart group, show loading/error state, and retain both timeframe buttons and PNG evidence. |
| Chart export and original PNG | Export supports review and external journaling. | Use a download icon and `Save chart PNG`; give full-size links descriptive names and images meaningful alt text. |
| Technical audit trail | Provenance is necessary but not the trader's primary task. | Keep it in a native collapsed disclosure after the trader-facing review. |

## Verification evidence

- Production Vite build succeeds.
- `axe-core` WCAG 2.0/2.1/2.2 A/AA scan reports zero violations on
  Overview, Journal, Calendar, Analytics, System, and an open decision drawer.
- Keyboard test proves: decision title receives initial focus; Tab enters the
  close control; Shift+Tab and Tab wrap within the drawer; Escape closes it;
  focus returns to the exact Review control; background inertness is removed.
- Mobile test at 390x844 proves no horizontal overflow and page navigation
  advances focus to the new H1.
- Desktop review at 1440x1000 covers all five pages; drawer and chart are also
  inspected at mobile width.
- Text tokens meet at least 4.5:1 contrast on their supported surfaces; control
  boundaries and meaningful graphical objects use at least 3:1 contrast or have
  an equivalent text representation.
- The Python suite and frontend production build remain required before commit.

## Research basis

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [WAI modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
- [WAI tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)
- [WAI: use of color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color)
- [WAI: non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast)
- [WAI: status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html)
- [Nielsen Norman Group: ten usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
- [TradingView chart accessibility](https://www.tradingview.com/charting-library-docs/latest/configuration/accessibility/)
- [TradeZella journal workflow](https://help.tradezella.com/en/articles/13863136-getting-started-with-tradezella)
- [Tradervue journal template](https://www.tradervue.com/trading-journal-template)
- [Edgewonk features](https://edgewonk.com/features)
