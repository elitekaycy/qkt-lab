# Deployment

Everything runs from `docker compose`. One command up, one file to edit.

```bash
git clone https://github.com/elitekaycy/qkt-lab && cd qkt-lab
codex login                   # once on the host; verify with `codex login status`
cp .env.example .env          # database + demo-broker settings; no model API key
$EDITOR lab.yaml              # the one file you edit
docker compose up -d
```

---

## The services

```
┌─ compose ────────────────────────────────────────────────────────────┐
│                                                                      │
│  mt5-gateway      elitekaycy/mt5-gateway-api:0.3.4   (published)     │
│      ▲                                                               │
│      │ HTTP                                                          │
│  lab              qkt-lab:local  ← qkt CLI + Codex CLI + python      │
│      │            one-shot container. bin/trade|join|distill|research │
│      │                                                               │
│  scheduler        supercronic + crontab → `docker compose run lab …` │
│      │                                                               │
│  postgres         decision + outcome. The machine's source of truth. │
│      │                                                               │
│  charts           caddy, static. Serves immutable PNG evidence.      │
│  journal-ui       React journal; reads the same Postgres directly.   │
└──────────────────────────────────────────────────────────────────────┘
```

`docker compose up` runs the loop and journal. There is one Postgres and no
closed-trade export job or secondary journal database.

## The lab image

The lab needs three runtimes in one place: the **qkt CLI** (JVM), the **Codex
CLI** (node), and **python** (the orchestration). Rather than reinstall a JRE, we
build on qkt's own runtime stage, which already has one:

```dockerfile
FROM qkt:local AS qkt
FROM debian:12-slim

# qkt CLI + its JRE, lifted from the qkt image
COPY --from=qkt /opt/java  /opt/java
COPY --from=qkt /opt/qkt   /opt/qkt
ENV JAVA_HOME=/opt/java  PATH="/opt/qkt/bin:/opt/java/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip nodejs npm git ca-certificates \
 && npm install -g @openai/codex@0.144.5 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt   # httpx, psycopg, mplfinance, pyyaml

WORKDIR /lab
ENTRYPOINT []          # qkt's runtime stage sets `qkt daemon` — we are not a daemon
```

`ENTRYPOINT []` matters: qkt's runtime image starts a daemon. The lab is a
one-shot container that runs, writes to disk, and exits.

---

## Four things that need a decision, not a default

### 1. `codex exec` needs a credential in the container

The default local path reuses the host's ChatGPT-managed Codex login:

```bash
codex login
codex login status
```

Compose bind-mounts only `~/.codex/auth.json` into the scheduler, read-write so
Codex can refresh it. Treat that file like a password. The agent is invoked with
`--ignore-user-config`, so unrelated host MCP servers and project preferences do
not enter the automated run.

Proposal-only sessions are ephemeral, read-only, and have shell, web, apps, and
subagents disabled. Research gets live web and a workspace-write sandbox rooted
at `memory/`; broker credential variables are stripped from its environment.
Because default Docker blocks Codex's nested bubblewrap namespaces, Compose uses
Codex's external-sandbox mode for research: the repo is mounted read-only, only
`memory/`, `state/`, and `.git` are writable, and the research shell is disabled.

### 2. Scheduling: supercronic, not `cron`

Plain `cron` in a container is a bad time — it swallows stdout, doesn't inherit the
container's env, and behaves badly as PID 1. Use **supercronic**: logs to stdout
(so `docker compose logs scheduler` just works), inherits env, exits properly.

```yaml
scheduler:
  image: qkt-lab:local
  entrypoint: ["/usr/local/bin/supercronic", "/lab/crontab"]
  volumes: [ ./:/lab, /var/run/docker.sock:/var/run/docker.sock ]
```

```crontab
0  6  * * *   /lab/bin/research
0  *  * * *   /lab/bin/trade ICM:XAUUSD
*/15 * * * *  /lab/bin/join
0  22 * * *   /lab/bin/distill
```

Note the schedule lives in **`lab.yaml`** and the crontab is *generated* from it —
otherwise you have two sources of truth for when things run, and they will drift.

### 3. `memory/` and `KILL` must be bind mounts, never named volumes

This is not a preference, it's a correctness requirement, and it's easy to get wrong.

**`memory/` is git-tracked.** It's the agent's intellectual history — every belief it
formed, every edge it drew, every time it changed its mind. If it lives in a named
volume, those commits are trapped inside Docker and `git log memory/map/real-yields.md`
on your host shows nothing. Bind-mount the repo.

The container also needs `git` and an identity to commit with, plus
`git config --global --add safe.directory /lab` (git refuses to operate on a
bind-mounted repo owned by a different uid).

**`KILL` must be visible across the boundary.** The emergency stop is `touch KILL` on
the host. If the container can't see that file appear, the emergency stop doesn't
exist. Bind mount, and the gate stats it on every cycle.

**`state/` (charts, logs)** can be a bind mount too — the charts service serves
the immutable PNG evidence.

### 4. qkt must be a *published* image, or nobody can run this

Done: the lab Dockerfile builds `FROM ghcr.io/elitekaycy/qkt:latest`, published
the way mt5-gateway publishes `elitekaycy/mt5-gateway-api:0.3.4`. There is no
build-from-source step in the critical path; `QKT_IMAGE` overrides the base for
development against a local qkt build. Licensing landed with it
([#8](../../issues/8) — qkt Apache-2.0, mt5-gateway MIT).

---

## Networking

`lab` reaches `mt5-gateway` over the compose network — `http://mt5-gateway:5001`,
which is what `qkt.config.yaml` already expects via `${QKT_*_URL}`.

The gateway is the only service that needs to reach the outside world for the broker.
RESEARCH needs outbound HTTPS for web search and keyless data. Nothing needs an inbound
port except the journal UI and the charts server, and both are localhost-only by default.
Set `LAB_CHARTS_PORT` if the default host port 8080 is already occupied.

## The state that matters

| path | mount | why |
|---|---|---|
| `memory/` | **bind** | git-tracked; the agent's history must be visible on the host |
| `KILL` | **bind** | the emergency stop must cross the boundary |
| `lab.yaml`, `prompts/`, `playbooks/` | **bind** | you edit these; no rebuild to change them |
| `state/charts/` | **bind** | served over HTTP; linked from the journal |
| postgres data | named volume | opaque, and that's fine |
| qkt state | named volume | qkt's own order journal; we don't read it |

The rule: **anything a human reads or writes is a bind mount. Anything only a machine
touches is a volume.**

## Acceptance

1. `docker compose up -d` on a clean machine brings up gateway, one Postgres,
   scheduler, charts, and the React journal.
2. `touch KILL` on the host stops the next cycle from placing an order.
3. The agent's memory edits appear as real commits in the host working tree.
4. `docker compose logs scheduler` shows every cycle's stdout.
5. No model API key in `.env`; Codex reuses the host login.

## Refs

Runtime design: [`RUNTIME.md`](RUNTIME.md)
Plan: [`PLAN.md`](PLAN.md)
