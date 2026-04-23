# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-22

Initial public release.

### Added

- **Sync client `MME`** with `save`, `inject`, `feedback`, `recent`, `delete`, `tags`.
- **Async client `AsyncMME`** — 1:1 mirror of the sync surface, built on `httpx.AsyncClient`.
- **Pydantic models** for every request and response shape: `Pack`, `PackItem`, `SaveResult`,
  `Tag`, `Score`, `Bounds`, `Rationale`, `InjectFilters`. Models accept extra fields so
  server-side additions don't break clients.
- **Exception taxonomy** rooted at `MMEError`: `MMEAuthError`, `MMEClientError`,
  `MMERateLimitError` (with `retry_after`), `MMEServerError`, `MMETimeoutError`,
  `MMEBudgetExceeded`. Every exception carries `status_code` and the parsed `response_body`.
- **Automatic auth** — exchanges your `mme_live_...` API key for a short-lived JWT on first
  use, caches it, and refreshes once on a 401 before re-raising.
- **`InjectFilters`** for narrowing retrievals by `section`, `status`, or `since` (datetime).
  Datetimes serialize to ISO-8601 over the wire.
- **LangChain integration** under the `[langchain]` extra: `MMESaveTool` and `MMEInjectTool`
  drop into any LangChain or LangGraph agent.
- **Configuration** — reads `RAILTECH_API_KEY` from the environment when no key is passed.
- **Tested** — 64 tests, 88% branch coverage, full mock coverage of the HTTP layer via
  `pytest-httpx`.
- **CI** on Python 3.9 / 3.10 / 3.11 / 3.12 (ubuntu-latest), with ruff + mypy --strict gates
  and a coverage floor of 80%.

[Unreleased]: https://github.com/gokulJinu01/railtech-mme-python/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/gokulJinu01/railtech-mme-python/releases/tag/v0.1.0
