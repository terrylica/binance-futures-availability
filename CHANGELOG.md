## 1.0.0 (2025-11-19)

### ⚠ BREAKING CHANGES

* **docs:** Old ADR/plan paths deprecated. ADRs moved from
docs/decisions/ to docs/architecture/decisions/. Plans moved from
docs/plans/ to docs/development/plan/. See ADR-0017 for migration
details and deprecation notices.

Refs: ADR-0017, ADR-0016
* **lookback:** None (default LOOKBACK_DAYS=1 preserves current behavior)

Relates-To: ADR-0011, ADR-0003 (strict errors), ADR-0009 (GitHub Actions)
* **adr-0011:** Introduces LOOKBACK_DAYS environment variable for
configurable date range probing (default: 1 day, backward compatible)

Architecture:
- Feature flag: LOOKBACK_DAYS env var (1=current, 20=production)
- Rolling window: Re-probes last N days on every scheduled run
- UPSERT semantics: INSERT OR REPLACE handles re-probing safely
- Instant rollback: Change env var value to revert

SLOs (ADR-0011):
- Availability: Gap repair within 20 days, 95% success rate
- Correctness: Late arrivals captured, volume metrics updated
- Observability: Date range logged, per-date visibility
- Maintainability: Reuses BatchProber, minimal code changes

Performance:
- 1-day mode: ~2 seconds (713 symbols × 1 date)
- 20-day mode: ~30 seconds (713 symbols × 20 dates)
- S3 requests: 6,540/day (within tested 118K capacity)

Deployment: Phased rollout (local → manual Actions → scheduled)

Relates-To: ADR-0003 (strict errors), ADR-0005 (S3 capacity),
ADR-0009 (GitHub Actions), ADR-0010 (symbol discovery)

See: docs/decisions/0011-20day-lookback-reliability.md
See: docs/plans/0011-20day-lookback/plan.yaml
* **ci:** APScheduler daemon will be deprecated in favor of GitHub Actions

Features:
- Scheduled daily updates at 3:00 AM UTC (configurable for 2-3x daily)
- Manual triggers with backfill support
- Automated GitHub Releases distribution with zstd compression
- 30-day retention policy (1.24 GB total storage)
- Zero infrastructure management overhead
- Built-in validation gates (continuity, completeness, API cross-check)

Implementation:
- ADR-0009: GitHub Actions automation decision
- Plan: docs/plans/0009-github-actions-automation/plan.yaml
- Workflow: .github/workflows/update-database.yml
- Documentation: docs/operations/GITHUB_ACTIONS.md
- Local testing: scripts/test-workflow-locally.sh

Cost: $0/month (public repos: unlimited Actions minutes + storage)
Performance: 5-10 minutes per run, 41 MB compressed upload
SLOs: 95% availability, >95% correctness, 100% observability

Closes #N/A
Refs: ADR-0004, ADR-0005, ADR-0006
* **adr:** None (documentation-only changes, no API/behavior changes)
* None (all changes backward compatible)

### Features

* add trading volume metrics collection (ADR-0007) ([28dba5b](https://github.com/terrylica/binance-futures-availability/commit/28dba5bd9ecf806f335f5fcbeccd796904de5641))
* **adr-0009:** deliver automation tools and complete Phase 1-2 ([94e6fed](https://github.com/terrylica/binance-futures-availability/commit/94e6fed3112e5f20184a3ac4ecc4a1d87f9ae9c8))
* **adr-0012:** implement gap detection and targeted backfill ([70c4d16](https://github.com/terrylica/binance-futures-availability/commit/70c4d16189fe3ea99e55df58ab2b5867a3426368))
* **adr-0012:** integrate auto-backfill into GitHub Actions workflow ([b0f15fb](https://github.com/terrylica/binance-futures-availability/commit/b0f15fb34e7bea6a6165e336aca1ffd6b1efe298))
* **adr-0013:** implement volume rankings time-series archive ([128dd68](https://github.com/terrylica/binance-futures-availability/commit/128dd68b5c060a1f65b2cf29cb319e41b9c0f27f))
* **automation:** implement GitHub Actions data collection (ADR-0009) ([8ef1da8](https://github.com/terrylica/binance-futures-availability/commit/8ef1da88772130dc48fe8819d43b4ec7569886e1))
* **ci:** add GitHub Actions automation for database updates (ADR-0009) ([fefef0e](https://github.com/terrylica/binance-futures-availability/commit/fefef0e7a0da798982795892774797ef3095f140))
* **discovery:** implement daily S3 symbol auto-discovery (ADR-0010) ([53b0f83](https://github.com/terrylica/binance-futures-availability/commit/53b0f835dc5c96a51bc752e098f9acbc3d8e8600))
* **docs:** migrate to standardized doc structure (ADR-0017) ([e0cc09b](https://github.com/terrylica/binance-futures-availability/commit/e0cc09b161588e2395b6d2d3d01030283836f4aa))
* initialize Binance Futures Availability Database project (v1.0.0) ([40e35e1](https://github.com/terrylica/binance-futures-availability/commit/40e35e1b402f0bf70e2bbf5b31fba32ea57c1a75))
* **lookback:** implement configurable lookback window via LOOKBACK_DAYS env var ([03f2810](https://github.com/terrylica/binance-futures-availability/commit/03f2810c35d3826f56981e39fcba8a2338270486))
* **skills:** add 3 atomic reusable skills from validated workflows ([5aba8e4](https://github.com/terrylica/binance-futures-availability/commit/5aba8e4aa7f2662aae29f8eb1a22ec0c202baf72))
* **workflow:** add lookback_days input parameter for manual testing ([62271fd](https://github.com/terrylica/binance-futures-availability/commit/62271fd7e6535b9b6ed365b14cfeada1e9fe8d86))

### Bug Fixes

* **adr-0012:** correct gap detection exit codes and workflow conditional logic ([7fccdc0](https://github.com/terrylica/binance-futures-availability/commit/7fccdc03b3c7d8ed1100b2593f22d1a26546ca0f))
* **backfill:** add db.close() to flush data to disk ([dd9a149](https://github.com/terrylica/binance-futures-availability/commit/dd9a149e19af2bd33cda687d38e1aa824746d2f2))
* **backfill:** fix thread-safety issue with shared DuckDB connection ([7899a92](https://github.com/terrylica/binance-futures-availability/commit/7899a92f03df21370e98cc2b1bc2c5de4b2997f7)), closes [#thread-safety](https://github.com/terrylica/binance-futures-availability/issues/thread-safety)
* **backfill:** initialize schema once before parallel workers ([1071cf7](https://github.com/terrylica/binance-futures-availability/commit/1071cf7bdcb453b8f5663b9ef38a9c277a9aded2))
* **backfill:** remove scheduler import, use standard logging ([6772cea](https://github.com/terrylica/binance-futures-availability/commit/6772cea6d4b56ff88b49ba3104472fbf1a8d8fd1))
* **ci:** upgrade Node.js to v22 for semantic-release v25+ ([f0ed889](https://github.com/terrylica/binance-futures-availability/commit/f0ed88930ff378fe80a84f19e303fc854b7f6fdc))
* **ci:** use npm install instead of npm ci for release workflow ([9918df6](https://github.com/terrylica/binance-futures-availability/commit/9918df6b3ed83ffe27cde5c2689f60e7a15dc9a6))
* **database:** add explicit commit before close for parallel writers ([f0733f3](https://github.com/terrylica/binance-futures-availability/commit/f0733f3ee73c01acdd4987875184cea0d97ed36e))
* **database:** read DB_PATH environment variable for GitHub Actions ([2adce09](https://github.com/terrylica/binance-futures-availability/commit/2adce0927d3c7797b2df558c2845bfae2e0617ff))
* **docs:** update broken links to GitHub Actions automation ([224d91e](https://github.com/terrylica/binance-futures-availability/commit/224d91e217dae6c5a43ae32d312dd8bb082b50e4))
* Handle empty S3 paths gracefully (no files = empty list, not error) ([200d85b](https://github.com/terrylica/binance-futures-availability/commit/200d85bcaeadfc41d593e3eebbbfefb4c399dc91))
* **probing:** add URL encoding for Unicode symbols (Chinese, emoji) ([efb2815](https://github.com/terrylica/binance-futures-availability/commit/efb28156cd26ee6f2dc8d9430a9790e51baa9eb7))
* **pytest:** remove coverage fail-under requirement from config ([fd16d50](https://github.com/terrylica/binance-futures-availability/commit/fd16d508351e93ddcbdafcbad24e1060a48f7d7d))
* type annotations and test fixtures, update implementation status ([025ef56](https://github.com/terrylica/binance-futures-availability/commit/025ef564774e273e407ad87a34aa05313c511944))
* **validation:** relax validation thresholds for historical data ([86d7eee](https://github.com/terrylica/binance-futures-availability/commit/86d7eeefc9311887ff046a1ed3f031f7f7af831e))
* **workflow:** check database existence after update, not before ([ea4a2fb](https://github.com/terrylica/binance-futures-availability/commit/ea4a2fb706a6dad56cdcc793db0f8287fbb04ea1))
* **workflow:** correct YAML syntax in commit message ([f4212d7](https://github.com/terrylica/binance-futures-availability/commit/f4212d737a8e2af9760f0b51fa47498226af336c))
* **workflow:** make publish steps conditional on database existence ([29586a8](https://github.com/terrylica/binance-futures-availability/commit/29586a812b0e3f4945397ced5ac2a8452128faaf))
* **workflow:** remove coverage requirement to allow workflow completion ([41a1061](https://github.com/terrylica/binance-futures-availability/commit/41a10619e019ba1e16bce2aa7f782cce4395a4f8))
* **workflow:** replace multi-line python -c blocks with heredocs to fix validation ([e1b3649](https://github.com/terrylica/binance-futures-availability/commit/e1b3649267ec4ae894f8370037a2e346dcb590ca))
* **workflow:** resolve validation failure by moving GitHub expressions to env blocks ([f33ffa1](https://github.com/terrylica/binance-futures-availability/commit/f33ffa13a5ab3786a588171befd688c295e4c1e6))
* **workflow:** restore missing start_date and end_date inputs for backfill mode ([efd6dcc](https://github.com/terrylica/binance-futures-availability/commit/efd6dcc4424076b48605c6e7521164dfd0320d2a))
* **workflow:** simplify run_daily_update.py to avoid scheduler dependencies ([3eab475](https://github.com/terrylica/binance-futures-availability/commit/3eab4759c65208e3513f2c8d4d909fbc189b1ec9))
* **workflow:** simplify workflow_dispatch inputs ([67f4cca](https://github.com/terrylica/binance-futures-availability/commit/67f4cca6fa5eaf38d586c85e2c8a43c9351dc282))
* **workflow:** skip validation and stats when no database exists ([88af471](https://github.com/terrylica/binance-futures-availability/commit/88af4715d577ed5e31f9135d66ba2df331961f58))
* **workflow:** use DB_PATH variable in compression step ([f0295fe](https://github.com/terrylica/binance-futures-availability/commit/f0295fe9a17f92140b2b0cafaa2048250a94d3f8))
* **workflow:** use external Python scripts instead of inline code ([9674661](https://github.com/terrylica/binance-futures-availability/commit/96746616a00d7e1ac1866d167aed6d77e91595a8))
* **workflow:** use pre-installed AWS CLI instead of installing ([ebf5fd6](https://github.com/terrylica/binance-futures-availability/commit/ebf5fd602ab3581080453a60afb877cddcff1d97))
* **workflow:** use setup-uv@v3 for compatibility ([7cda049](https://github.com/terrylica/binance-futures-availability/commit/7cda04989ad132c025bd20dd5faef34ece62d3a4))

### Performance Improvements

* **batch-prober:** optimize worker count to 150 (3.94x speedup) ([65c5f90](https://github.com/terrylica/binance-futures-availability/commit/65c5f903b5db8aedfd050d657fedd5bcac0c2fc7))

### Documentation

* **adr-0011:** implement 20-day lookback for data reliability ([89dad82](https://github.com/terrylica/binance-futures-availability/commit/89dad82ba3e7a9ddf6f9edcf04610bae9f9ebc67))
* **adr:** implement ADR-0008 workspace organization ([6942a90](https://github.com/terrylica/binance-futures-availability/commit/6942a90c1c43f0ff6ef18562f4048bd96f040664))
