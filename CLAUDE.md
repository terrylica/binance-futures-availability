# Binance Futures Availability Database

Daily availability (and 1d-kline volume) of every Binance USDT-M perpetual on Binance Vision S3, 2019-09-25 to yesterday, as one DuckDB table published to the `latest` GitHub Release. User-facing docs: [README.md](README.md).

## Where things live

- **Decisions**: [`docs/architecture/decisions/`](docs/architecture/decisions/) (MADR; the newest supersede older ones; read the relevant ADR before changing behavior). Start with [ADR-0028](docs/architecture/decisions/0028-upsert-integrity-and-volume-collection.md).
- **Schema SSoT**: [`src/binance_futures_availability/database/schema.py`](src/binance_futures_availability/database/schema.py), documented in [`docs/schema/availability-database.schema.json`](docs/schema/availability-database.schema.json)
- **Pipeline**: [`.github/workflows/update-database.yml`](.github/workflows/update-database.yml), daily 03:00 UTC: discover symbols → probe a 20-day lookback → fill volume → validate → rankings → publish → Pushover
- **Architecture**: [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) · **Operations**: [`docs/operations/`](docs/operations/) · **Troubleshooting**: [`docs/guides/TROUBLESHOOTING.md`](docs/guides/TROUBLESHOOTING.md)

## Local gate (run before every push)

```bash
./scripts/check.sh        # ruff check + format --check + full pytest (coverage ratchet)
```

GitHub Actions runs only the data pipeline, never tests or lint. Python comes from `.python-version` via uv; Node (semantic-release only) comes from `.prototools`.

## Operating the pipeline

```bash
gh workflow run update-database.yml -f update_mode=daily                                   # re-run now
gh workflow run update-database.yml -f update_mode=daily -f volume_start_date=2020-01-01   # volume catch-up
gh workflow run update-database.yml -f update_mode=backfill -f start_date=2024-01-01       # AWS CLI backfill
```

## Invariants and pitfalls (each one cost real data)

- **Never index a mutable, non-key column of `daily_availability`.** DuckDB 1.4.x `INSERT OR REPLACE` silently skipped indexed columns, which corrupted `available` for ~10 months (ADR-0028).
- **Upserts go through `AvailabilityDatabase.insert_batch` only** (explicit `ON CONFLICT`; volume is `COALESCE`d, so re-probes keep it).
- **`available ⇔ status_code = 200`** and the other invariants in `validation/integrity.py` are a hard gate: violation means exit 1, nothing published. Every other validation finding is informational (ADR-0003).
- **S3 publishes T+1 and sometimes later**: a first-probe 404 is normal, and the 20-day lookback (ADR-0011) re-probes it. Anything derived from the DB must tolerate late arrivals, which is why rankings regenerate in full every run.
- **Volume is supplementary**: fetch failures are logged and retried next run, never blocking availability. Probe errors raise (ADR-0003: no retries, no silent fallbacks).
- **Delisted symbols are probed forever** (ADR-0010); ~1,000 rows per date is expected.
