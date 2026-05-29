# Contributing to Eero API

Thank you for your interest in contributing to Eero API! This document provides guidelines and instructions for contributing.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Commit Messages](#commit-messages)
- [Pull Requests](#pull-requests)
- [Release Process](#release-process)

## 📜 Code of Conduct

Please be respectful and constructive in all interactions. We're all here to build something great together.

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Node.js 20+ (for commit linting in CI)

### Setup

```bash
# Clone the repository
git clone https://github.com/fulviofreitas/eero-api.git
cd eero-api

# Create virtual environment and install dependencies
uv sync --extra dev

# Or with pip
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/eero --cov-report=html

# Run specific test file
uv run pytest tests/api/test_auth.py -v
```

### Code Quality

```bash
# Format code
uv run black src/ tests/
uv run isort src/ tests/

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/
```

## 🔄 Development Workflow

1. **Fork** the repository
2. **Create a branch** from `master`:
   ```bash
   git checkout -b feat/my-new-feature
   ```
3. **Make changes** and commit using [Conventional Commits](#commit-messages)
4. **Push** to your fork
5. **Open a Pull Request** to `master`

## 📝 Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/) for automatic semantic versioning. Your commit messages determine how the version number changes.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description | Version Bump |
|------|-------------|--------------|
| `feat` | New feature | **Minor** (1.0.0 → 1.1.0) |
| `fix` | Bug fix | **Patch** (1.0.0 → 1.0.1) |
| `perf` | Performance improvement | **Patch** |
| `docs` | Documentation only | None |
| `style` | Formatting (no code change) | None |
| `refactor` | Code restructuring | None |
| `test` | Adding/updating tests | None |
| `build` | Build system changes | None |
| `ci` | CI configuration | None |
| `chore` | Maintenance | None |
| `revert` | Revert previous commit | None |

### Breaking Changes

For breaking changes, add `!` after the type or include `BREAKING CHANGE:` in the footer:

```bash
# Using exclamation mark
feat!: redesign authentication API

# Using footer
feat: redesign authentication API

BREAKING CHANGE: The login() method now requires an options object instead of positional arguments.
```

Breaking changes trigger a **Major** version bump (1.0.0 → 2.0.0).

### Examples

```bash
# Feature with scope
feat(api): add network diagnostics endpoint

# Bug fix
fix: resolve timeout in device discovery

# Documentation
docs: update installation instructions

# Feature with body
feat(profiles): add parental control support

Add support for managing parental control profiles including:
- Content filtering
- Time limits
- App blocking

Closes #42

# Breaking change
feat!: require Python 3.11+

BREAKING CHANGE: Dropped support for Python 3.10
```

### Interactive Commit (Optional)

If you prefer a guided experience, use commitizen:

```bash
# Install with dev dependencies
uv sync --extra dev

# Make a commit interactively
uv run cz commit
```

## 🔀 Pull Requests

### PR Title

Your PR title should also follow Conventional Commits format. When using squash merge (default), the PR title becomes the commit message.

### PR Checklist

Before submitting:

- [ ] Tests pass locally (`uv run pytest`)
- [ ] Code is formatted (`uv run black src/ tests/`)
- [ ] Linting passes (`uv run ruff check src/ tests/`)
- [ ] Documentation is updated (if needed)
- [ ] Commit messages follow Conventional Commits

### Review Process

1. **Automated checks** run on your PR
2. **Maintainers review** your changes
3. **Address feedback** if any
4. **Squash and merge** when approved

## 🏷️ Release Process

Releases are **fully automated** based on commit messages. Here's how it works:

### Workflow Chain

```
🧪 CI Pipeline  ──→  🚀 Release
     ✅                  ✅
```

### Automatic Versioning

1. When you push to `master` (or merge a PR), CI runs
2. If all checks pass, the release workflow triggers
3. It analyzes commits since the last release
4. Determines the version bump based on commit types
5. Updates `pyproject.toml` and `src/eero/__init__.py`
6. Generates/updates `CHANGELOG.md`
7. Creates a Git tag (e.g., `v1.2.0`)
8. Creates a GitHub Release

### Version Bump Rules

| Commits Since Last Release | Version Change |
|---------------------------|----------------|
| Only `fix:`, `perf:` | Patch (1.0.0 → 1.0.1) |
| At least one `feat:` | Minor (1.0.0 → 1.1.0) |
| Any breaking change (`feat!:`, `BREAKING CHANGE:`) | Major (1.0.0 → 2.0.0) |
| Only `docs:`, `chore:`, `ci:`, etc. | No release |

### Manual Release (Emergency)

Maintainers can trigger a manual release via GitHub Actions:

1. Go to **Actions** → **🚀 Release**
2. Click **Run workflow**
3. Optionally select "Dry-run mode" to simulate
4. Click **Run workflow**

## 🤖 Reporting issues — what happens after you file one

This repo runs two AI-driven GitHub Actions workflows that may interact with your issue:

### Triage agent (always runs, ~30 seconds)

When you open an issue, an automated triage agent reads it and:

- Applies categorisation labels (`bug`, `documentation`, `enhancement`, `question`, `security`, etc.)
- Posts a friendly acknowledgement comment so you know it's been seen

The labels and comment are purely informational. A maintainer will still review and respond.

### Draft-fix agent (only on certain bugs, ~5–10 minutes)

If your issue is labeled `bug` AND looks well-scoped (clear reproduction steps, small surface area, not flagged `critical`), the triage agent will also apply a `try-fix` label. That triggers an autonomous coding agent which will:

1. Browse the repo to understand the code paths involved
2. Propose a focused fix and add/update a test for it
3. Run the test suite and linter — and only commit if both pass
4. Open a **DRAFT** pull request linked to your issue with `Closes #<n>`

A maintainer will then review the draft PR — it's a starting point, not a merge-ready submission. You may comment on it or wait for the maintainer to iterate.

**If you'd rather opt out:** add a comment asking for the `try-fix` label to be removed. A maintainer can take it off and no further automated work will happen.

**If you'd like to invite a draft-fix attempt on a bug that wasn't auto-flagged:** ask in a comment and a maintainer can apply the label manually.

For full architecture and operating notes, see `claude/rules/agentic-workflows.md` in the [private context repo](https://github.com/fulviofreitas/eero-api-context).

## ❓ Questions?

Open an issue or start a discussion. We're happy to help!
