# Concurrent first-request bootstrap

Type: observed local browser-test incident. Date: 2026-10-02. Scope: synthetic demo initialization; no private data.

## What happened

The initial browser test made concurrent requests while React StrictMode exercised initialization. Multiple threads missed the same functools.lru_cache entry. Each started schema bootstrap before either result was cached. One failed with SQLite `table members already exists`, producing an API error during page initialization.

## Root cause

lru_cache protects its cache bookkeeping but does not serialize execution of concurrent misses. Schema create-if-missing is also not an application initialization lock. The bootstrap bundled schema creation and demo token seeding, so concurrent misses could create independent stores or rotate tokens during startup.

## Corrective action

Serialize the cached runtime factory with a process-local lock. Add `test_parallel_first_requests_share_one_bootstrap`, which calls initialization from eight threads against a fresh database and requires one Store object. The reproduction failed before the fix and passed afterward. The browser submission→processing→approval flow then passed.

## Limits and follow-up

This lock is local to one process. Demo deployment is intentionally one API process. It does not solve coordination of demo tokens across several API instances; private deployments must migrate/provision independently of API startup and use a coordinated identity provider. No invented database-exhaustion incident or fabricated before/after failure percentage is attached to this event.
