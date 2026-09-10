# 🤝 Contributing

Development setup, the checks CI runs, and the conventions this repository enforces.

---

## 🧰 Setup

Python **3.12+** is required (3.13 and 3.14 are also supported and tested).

```bash
git clone https://github.com/fulviofreitas/eero-api.git
cd eero-api
pip install -e ".[dev]"
```

The `[dev]` extra installs `pytest`, `pytest-asyncio`, `pytest-cov`, `black`, `isort`, `mypy`,
`ruff`, `rich`, `click`, and `commitizen`.

---

## ✅ The Checks

Run all of these before opening a pull request — CI runs the same commands and a failure in any
of them blocks the merge.

```bash
pytest                                          # full suite
ruff check .                                    # lint
black .                                         # format
mypy src/                                       # type-check
```

| Command | What it gates |
|---------|---------------|
| 🧪 `pytest` | The full suite, unit and integration |
| 🔍 `ruff check .` | Lint |
| 🎨 `black .` | Formatting |
| 🏷️ `mypy src/` | Type-checking of the package source |

### Useful test invocations

```bash
pytest tests/api/                               # unit tests only
pytest tests/integration/                       # integration tests only
pytest --cov=eero --cov-report=term-missing     # coverage
pytest -k "auth and login"                      # pattern match
pytest -x -v                                    # stop on first failure, verbose
```

---

## 🧪 Writing Tests

Tests mirror the source layout — `tests/api/test_<domain>.py` for `src/eero/api/<domain>.py`.

- Mock at the **network boundary** only. Do not mock internal modules.
- `pytest-asyncio` runs in auto mode, so `async def test_…` needs no decorator.
- Use `AsyncMock` for coroutines and async context managers, `MagicMock` for sync dependencies.
- Never make real calls to `api-user.e2ro.com`. No test may depend on a real account, a real
  token, or the network.
- Cover the failure paths, not just the happy path: auth errors, rate limits, timeouts,
  malformed or partial response envelopes.

```python
mock_client = AsyncMock()
mock_client.__aenter__ = AsyncMock(return_value=mock_client)
mock_client.__aexit__ = AsyncMock()
```

> 💡 **Tip:** Because every method returns a raw envelope, fixtures should be realistic
> `{"meta": ..., "data": ...}` dicts rather than tidy flat objects. See
> [Raw Response Format](Raw-Response-Format).

---

## 📝 Commit Messages

Commits must follow [Conventional Commits](https://www.conventionalcommits.org/) — `commitlint`
runs in CI and a non-conforming message fails the build, which skips every other job.

```
feat(devices): add bulk block support
fix(auth): retry once on session refresh
docs(wiki): correct the caching examples
chore(deps): bump aiohttp
```

Releases and version bumps are automated from these messages, so the type prefix determines the
next version number. `commitizen` is available if you want the interactive prompt:

```bash
cz commit
```

---

## 🏛️ Code Conventions

- **Async everywhere.** All network operations are `async`/`await`.
- **Raw returns.** Every API method returns `Dict[str, Any]` — the unmodified upstream response.
  Do not add parsing, reshaping, or model classes; that is the consumer's job. See
  [Raw Response Format](Raw-Response-Format).
- **Composition over inheritance.** New functionality becomes a domain API class composed into
  `EeroAPI`, not a deeper inheritance chain.
- **One domain per module.** `src/eero/api/<domain>.py` holds one focused class.
- **`network_id` is a trailing optional kwarg**, never the first positional argument. See
  [Network Targeting](Network-Targeting).
- **Naming:** `snake_case` for functions and modules, `PascalCase` for classes,
  `SCREAMING_SNAKE_CASE` for constants.
- **Never log secrets.** Route logging through the helpers in `src/eero/logging.py`. See
  [Logging and Security](Logging-and-Security).

---

## ➕ Adding a Domain API

1. Create `src/eero/api/<domain>.py` with a class extending `AuthenticatedAPI`.
2. Register it on `EeroAPI` in `src/eero/api/__init__.py`.
3. Add thin `EeroClient` wrappers in `src/eero/client.py` if the domain is user-facing, keeping
   `network_id` as the trailing optional kwarg and wiring `_ensure_network_id`.
4. Add tests under `tests/api/`.
5. Document it in [API Reference](API-Reference), and in [Python API](Python-API) if it warrants
   a task-oriented section.

---

## 📚 Editing This Wiki

The wiki is **generated from the repository**, not edited on GitHub. Source lives in
[`wiki/`](https://github.com/fulviofreitas/eero-api/tree/master/wiki); the
`sync-wiki` workflow publishes it on every push to `master` that touches `wiki/**`.

- Edits made directly in the GitHub wiki UI will be overwritten on the next sync.
- `_Sidebar.md` and `_Footer.md` render on every page — update `_Sidebar.md` when adding a page.
- Links are wiki-relative and bare: `[Python API](Python-API)`.
- Every code example must be correct against the current source. A broken example is worse than
  no example — this wiki had to be rebuilt once because its examples drifted several major
  versions behind the SDK.

---

## 🤖 Automation

Two AI-driven workflows run on issue events:

- **Issue triage** labels new issues and posts an acknowledgement.
- **Draft-fix** opens a draft PR for issues labelled `try-fix`, runs lint and tests, and links
  the issue. Every draft PR is reviewed by a maintainer before merge.

---

## 🔗 Related Pages

- [Home](Home) — Overview and quick start
- [API Reference](API-Reference) — The surface you are extending
- [Raw Response Format](Raw-Response-Format) — The architectural rule behind every return type
- [Logging and Security](Logging-and-Security) — Safe logging requirements
- [Ecosystem](Ecosystem) — Downstream consumers affected by your changes
