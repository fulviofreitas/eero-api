# Image for the Draft-Fix workflow on eero-api.
#
# Pre-bakes the heavy tooling (Claude Code CLI, gh CLI, Python toolchain)
# AND the repo's pip dependencies so the workflow runs faster and the
# agent has more turn budget for actual code work (no npm/pip install
# turns burned at runtime).
#
# Built and pushed to ghcr.io by .github/workflows/build-draft-fix-image.yml
# on changes to this Dockerfile, on changes to pyproject.toml, weekly,
# and on workflow_dispatch.
#
# Consumed by .github/workflows/draft-fix.yml via the `container:` key.

FROM node:24-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Base OS tooling: git, jq, curl, python, build essentials for native deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg git jq \
      python3 python3-pip python3-venv python3-dev \
      build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI — needed by draft-fix.yml's gh issue/pr/comment steps.
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
      gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI — the agent runtime that draft-fix.yml invokes.
RUN npm install -g --no-audit --no-fund @anthropic-ai/claude-code \
    && claude --version

# Pre-install the repo's Python dependencies into the system site-packages.
# We install only the deps (not the project itself); the project will be
# installed editably by the workflow after actions/checkout so any new
# code in the checked-out workspace is picked up.
WORKDIR /tmp/preinstall
COPY pyproject.toml ./
RUN python3 -m pip install --break-system-packages --upgrade pip \
    && (python3 -m pip install --break-system-packages '.[dev]' \
        || python3 -m pip install --break-system-packages '.' \
        || true) \
    && rm -rf /root/.cache/pip

# actions/checkout writes to /github/workspace by default in container jobs.
WORKDIR /github/workspace
