# Deployment

Everything runs from `docker compose`. One command up, one file to edit.

```bash
git clone https://github.com/elitekaycy/qkt-lab && cd qkt-lab
cp .env.example .env          # DB DSNs + your Claude token. No API keys.
$EDITOR lab.yaml              # the one file you edit
docker compose up -d
```

---

## The services

```
┌─ compose ────────────────────────────────────────────────────────────┐
│                                                                      │
│  mt5-gateway      elitekaycy/mt5-gateway-api:0.3.3   (published)     │
│      ▲                                                               │
│      │ HTTP                                                          │
│  lab              qkt-lab:local  ← qkt CLI + claude CLI + python     │
│      │            one-shot container. bin/trade|join|distill|research │
│      │                                                               │
│  scheduler        supercronic + crontab → `docker compose run lab …` │
│      │                                                               │
│  postgres         decision + outcome. The machine's source of truth. │
│      │                                                               │
│  charts           caddy, static. Serves state/charts over HTTP —     │
│                   Deltalytix images[] takes URLs, not paths.         │
│                                                                      │
│  ── profile: journal (optional; the loop runs without it) ───────    │
│  deltalytix       self-hosted UI. CC BY-NC, so: a plugin.            │
│  deltalytix-db    its own postgres. Separate from ours, on purpose.  │
└──────────────────────────────────────────────────────────────────────┘
```

`docker compose up` runs the loop. `docker compose --profile journal up` also
brings the UI. Nothing in the loop breaks if the journal is down — that's the
whole point of it being a profile.

## The lab image

The lab needs three runtimes in one place: the **qkt CLI** (JVM), the **claude
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
 && npm install -g @anthropic-ai/claude-code \
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

### 1. `claude -p` needs a credential in the container

This is the one credential in the system, and it's worth being precise: **it is not
an API key** — it's your Claude subscription, via `CLAUDE_CODE_OAUTH_TOKEN`.

```bash
claude setup-token          # on the host, once
# paste into .env as CLAUDE_CODE_OAUTH_TOKEN
```

Spike S0.4 answered the two questions this rested on: headless `claude -p`
works inside the container with only that token (or a `~/.claude` mount, which
compose sets up and which also self-refreshes), and it rides the subscription
pool — no API key anywhere. If either ever regresses, say so out loud: it
breaks the no-keys property and changes what this repo can honestly claim.

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

**`state/` (charts, logs)** can be a bind mount too — the charts service serves it and
Deltalytix links to it.

### 4. qkt must be a *published* image, or nobody can run this

Done: the lab Dockerfile builds `FROM ghcr.io/elitekaycy/qkt:latest`, published
the way mt5-gateway publishes `elitekaycy/mt5-gateway-api:0.3.3`. There is no
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

1. `docker compose up -d` on a clean machine brings up gateway, postgres, scheduler,
   charts — and the loop runs on schedule with no host-side setup beyond `.env`.
2. `docker compose --profile journal up -d` additionally brings the UI, and stopping
   it **does not stop the loop**.
3. `touch KILL` on the host stops the next cycle from placing an order.
4. The agent's memory edits appear as real commits in the host working tree.
5. `docker compose logs scheduler` shows every cycle's stdout.
6. No API keys in `.env` — only DB DSNs and the Claude subscription token.

## Refs

Runtime design: [`RUNTIME.md`](RUNTIME.md)
Plan: [`PLAN.md`](PLAN.md)
