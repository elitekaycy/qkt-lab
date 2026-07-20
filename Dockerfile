# The lab image: qkt CLI (JVM) + Codex CLI (node) + python orchestration.
#
# QKT_IMAGE must carry the `qkt bot` command group; the published image does.
# Override to pin a version, or to a local build when developing against qkt.
ARG QKT_IMAGE=ghcr.io/elitekaycy/qkt:latest
ARG CODEX_VERSION=0.144.5
FROM ${QKT_IMAGE} AS qkt

FROM debian:12-slim
ARG CODEX_VERSION

COPY --from=qkt /opt/java /opt/java
COPY --from=qkt /opt/qkt /opt/qkt
ENV JAVA_HOME=/opt/java/runtime PATH="/opt/qkt/bin:/opt/java/runtime/bin:/usr/local/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv git ca-certificates curl nodejs npm \
 && npm install -g "@openai/codex@${CODEX_VERSION}" \
 && curl -fsSL -o /usr/local/bin/supercronic \
      https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 \
 && chmod +x /usr/local/bin/supercronic \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /lab
COPY pyproject.toml ./
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir \
      pyyaml "psycopg[binary]" httpx mplfinance pandas numpy scipy matplotlib
ENV PATH="/opt/venv/bin:${PATH}"

# git identity for research-cycle commits to the bind-mounted memory/;
# safe.directory because the mount is owned by the host uid.
RUN git config --global user.name "qkt-lab" \
 && git config --global user.email "lab@localhost" \
 && git config --global --add safe.directory /lab

# The repo itself is bind-mounted at /lab at runtime — memory/ commits must land
# in the host working tree, and lab.yaml/prompts edits must not need a rebuild.
ENTRYPOINT []
CMD ["bash"]
