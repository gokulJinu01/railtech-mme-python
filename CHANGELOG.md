# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-04-23

End-to-end verification against the live backend surfaced two real bugs in
the 0.1.0 surface; this release patches both before any wider launch.

### Fixed

- **`recent()` no longer crashes on real responses.** The 0.1.0 implementation
  parsed `GET /memory/recent` results as :class:`PackItem`, but the server
  returns raw memory blocks with `content` (not `title`) and structured
  :class:`Tag` objects (not flat strings). Any real call raised
  `pydantic.ValidationError`. Now returns a new :class:`MemoryBlock` model
  that matches the wire shape exactly.
- **README quickstart now returns items on a fresh account.** The 0.1.0
  example saved one fact about chocolate and queried `"What do I like to
  eat?"` — a paraphrase that doesn't activate the `dark_chocolate` /
  `food_item` tags MME assigns. The new quickstart saves three related
  facts and queries with concrete keywords (`food`, `allergies`) that
  reliably retrieve, plus a note explaining the tag-graph cold-start
  property.

### Added

- **`MemoryBlock` model** — full wire shape for raw stored memories:
  `id`, `content`, `tags: list[Tag]`, `tags_flat`, `section`, `status`,
  `source`, `importance`, `org_id`, `user_id`, `hash`, `created_at`,
  `updated_at`. Exported from the package root.
- **`SaveResult` expanded** — `success: bool`, `org_id`, `user_id`,
  `tags: list[Tag]`, `tags_flat`. The fields were already arriving on the
  wire (and accepted via `extra="allow"`) but were untyped; users had to
  reach into `.model_dump()` to read them. Now first-class.

### Notes

- `recent()` return type changed from `list[PackItem]` to `list[MemoryBlock]`.
  This is a breaking change in name, but in 0.1.0 the method raised an
  exception on every real call, so no working code can break.
- All existing tests passed against the new shapes after updating the
  mocks to match what the server actually emits (the 0.1.0 mocks lied —
  fixed in this release).

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

[Unreleased]: https://github.com/gokulJinu01/railtech-mme-python/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/gokulJinu01/railtech-mme-python/releases/tag/v0.1.1
[0.1.0]: https://github.com/gokulJinu01/railtech-mme-python/releases/tag/v0.1.0
