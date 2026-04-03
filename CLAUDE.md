# CLAUDE.md

## Project identity
This repo builds a Polymarket trading system incrementally.

The current objective is NOT the full multi-strategy platform.
The current objective is V1 only:

Late-Stage Carry Bot
- paper trading only
- no live capital
- no ML
- no wallet tracking
- no sentiment pipeline
- no dashboard-first work
- no premature abstraction

Claude must optimize for validating one real edge with minimal moving parts.

## Current V1 thesis
Build the simplest robust strategy first:
- monitor active Polymarket markets
- identify markets within 48 hours of resolution
- estimate likely outcome from external sources or simple heuristics
- if likely outcome probability is high enough and market price is below threshold, generate a paper trade
- hard cap size at $200 per trade
- hold to simulated resolution
- log every decision

## What success means right now
Done means:
1. market data can be pulled reliably
2. market state is persisted
3. carry opportunities can be detected deterministically
4. paper trades are generated through the same strategy pipeline that live trading would use later
5. every signal, decision, and paper order is logged
6. basic risk gates exist
7. tests cover touched logic
8. no unrelated refactors

## Build order
Strict priority order:
1. Polymarket API client
2. Market state database and cache
3. Late-stage carry signal module
4. Paper trade executor
5. Audit log
6. Basic risk manager
7. Kill switch
8. Backtest harness
9. Only after V1 is stable: multi-outcome arb
10. Only later: cross-market arb, sentiment, wallet tracking, live execution

## Architecture constraints
The intended architecture is:
- data ingestion layer
- market state store
- stateless signal engine
- strategy engine
- risk manager as mandatory gatekeeper
- execution router
- append-only audit log

Rules:
- signal modules must be stateless
- risk manager must gate every order
- only execution router can talk to Polymarket
- paper and live should share the same order path with a backend switch
- audit logging is append-only

## Session protocol
One Claude Code session = one mission.

Never mix unrelated work in a single session.
If the task changes domain, clear context or start a new session.

Mission examples:
- build-polymarket-client
- add-market-store
- implement-carry-signal
- add-paper-executor
- add-risk-gates
- write-carry-tests

## How Claude should work
For any non-trivial task:
1. inspect only the relevant files
2. produce a plan first
3. identify smallest safe implementation
4. implement with minimal diffs
5. run narrow verification first
6. summarize what changed, what remains, and any risks

Do not start coding immediately on risky work.

## Plan-first policy
Always plan first for:
- schema changes
- new background workers
- concurrency changes
- auth/secrets handling
- external API integration
- risk manager changes
- execution router changes
- anything affecting paper/live trade path

Plan format:
1. goal
2. files to inspect
3. smallest implementation path
4. test plan
5. risks / rollback

## Code style
- prefer explicit, boring code over framework cleverness
- minimal diffs
- no speculative abstractions
- no generic plugin architecture until there are at least 2 real implementations
- keep modules small and testable
- prefer deterministic functions for signal logic
- preserve comments that explain trading assumptions
- do not silently change thresholds or risk values

## Forbidden behavior
Do not:
- build dashboards before core trading logic
- add machine learning before simple heuristics are validated
- add social sentiment pipelines in V1
- add wallet intelligence in V1
- refactor the entire repo because one file feels “unclean”
- create live trading code paths unless explicitly requested
- bypass risk manager
- write to external systems outside approved integration modules

## Repository assumptions
Suggested layout:

config/
  settings.yaml
  market_taxonomy.yaml
  secrets.env

src/
  data/
  signals/
  strategy/
  execution/
  risk/
  backtest/
  audit/
  utils/

tests/

If the repo differs, adapt without forcing a rewrite.

## Verification rules
After changes:
- run tests for touched area first
- then broader integration checks if needed
- if there are no tests yet, add focused tests for new core logic
- do not claim something works without running or explaining verification

## What to preserve during compaction
When context is summarized, preserve:
- current mission
- touched files
- pending decisions
- failing tests
- thresholds and risk constants
- open bugs
- assumptions about Polymarket API behavior
- whether code is paper-trade-only or live-capable

## Preferred response style
Be a repo-native systems operator.
Be concise, concrete, and skeptical.
Show:
- what you inspected
- what you changed
- how you verified it
- what remains risky

Avoid vague optimism.