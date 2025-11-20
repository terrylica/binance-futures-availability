# Data Quality & Observability Tools: Detailed Comparison Matrix

**Report Date**: 2025-11-20
**For Project**: Binance Futures Availability Database

---

## 1. Data Quality Frameworks Comparison

### Feature Matrix

| Feature                     | Great Expectations | Soda Core                  | DQOps           | Elementary               |
| --------------------------- | ------------------ | -------------------------- | --------------- | ------------------------ |
| **Setup Time**              | 1-2 weeks          | 1-2 days                   | 3-5 days        | 1 week                   |
| **Learning Curve**          | Steep (Python)     | Gentle (YAML/SQL)          | Medium          | Medium                   |
| **Cost**                    | Free (OSS)         | Free Core / $50-1999 Cloud | Free / $500+    | Free OSS / Cloud pricing |
| **Deployment**              | Python, Docker     | CLI, Airflow, dbt          | Cloud SaaS      | Python, Cloud            |
| **Code-First**              | Yes                | SQL/YAML                   | GUI-First       | dbt-First                |
| **DuckDB Support**          | Yes                | Yes                        | Yes             | No (dbt only)            |
| **GitHub Actions Friendly** | Yes (Python)       | Yes (CLI)                  | No (Cloud only) | No (dbt only)            |

### Detailed Comparison

#### Great Expectations (GX)

**When to Use**:

- Complex statistical validation (distribution, outliers)
- Custom Python logic for edge cases
- Need beautiful Data Docs for compliance
- Team comfortable with Python

**Strengths**:

```python
✅ Checkpoint-based testing (idempotent like Binance's backfill)
✅ Configurable data contexts
✅ Excellent error messages
✅ Full debugging via Python REPL
✅ Suite-based organization (like test suites)
✅ Automatic data profiling
```

**Weaknesses**:

```
❌ Steep learning curve (Data Contexts, Batch Requests, Expectation Suites)
❌ Verbose configuration for simple checks
❌ Requires Python knowledge
❌ Slow to get first check working
❌ Heavy dependencies
```

**Integration Complexity**: 8/10 (requires Python expertise)

**Example Usage**:

```python
from great_expectations.core.batch import RuntimeBatchRequest

context = gx.get_context()
validator = context.get_validator(
    batch_request=RuntimeBatchRequest(
        datasource_name="duckdb_source",
        data_connector_name="daily_availability"
    )
)

# Symbol must be USDT future
validator.expect_column_values_to_match_regex("symbol", r"[A-Z]+USDT$")

# No nulls allowed
validator.expect_column_values_to_not_be_null("date")

# Row count reasonable
validator.expect_table_row_count_to_be_between(100, 700)

# File size must be positive (no corrupted files)
validator.expect_column_values_to_be_greater_than("file_size_bytes", 0)

# Custom expectation: 90% of symbols should be available
validator.expect_column_mean_to_be_between("available", 0.90, 1.0)

checkpoint = context.add_checkpoint(
    name="daily-availability-checks",
    validations=[validator]
)
checkpoint.run()
```

---

#### Soda Core

**When to Use**:

- Quick implementation needed (1-2 days)
- Team comfortable with SQL
- Freshness, volume, validity checks
- CI/CD pipeline integration
- Like dbt tests but for broader data quality

**Strengths**:

```yaml
✅ YAML-based configuration (intuitive)
✅ Fast to implement (minutes for first check)
✅ SQL WHERE clauses (familiar to analysts)
✅ CLI tool (perfect for GitHub Actions)
✅ Custom SQL checks
✅ Python UDFs for complex logic
✅ Minimal dependencies
```

**Weaknesses**:

```
❌ Less flexible than Python for complex logic
❌ Smaller ecosystem
❌ Cloud version pricing can add up
```

**Integration Complexity**: 3/10 (YAML + CLI = simple)

**Example Usage**:

```yaml
# soda-checks.yml

data_sources:
  duckdb:
    type: duckdb
    connection:
      database: ~/.cache/binance-futures/availability.duckdb

checks for daily_availability:
  # Freshness check (ADR-0011: data < 24 hours old)
  - freshness(last_modified) < 1 h:
      name: "Data published within 1 hour"

  # Volume check (completeness)
  - row_count between 100 and 700:
      name: "Expected symbol count per date"

  # Null check
  - missing_count(date) = 0
  - missing_count(symbol) = 0

  # Pattern validation
  - invalid_count(symbol) = 0 where symbol like '%USDT'

  # File size anomalies (statistical)
  - anomaly_detection(file_size_bytes):
      algorithm: zscore
      threshold: 3
      direction: "both"
      name: "File size outliers"

  # Custom SQL check
  - duplicate_count(date, symbol) = 0:
      name: "No duplicate symbol/date pairs (primary key)"

  # Volume metric checks (ADR-0006)
  - missing_percent(file_size_bytes) < 5
  - missing_percent(last_modified) < 5
```

**CLI Usage**:

```bash
# Run checks
soda scan -c duckdb-config.yml soda-checks.yml

# Output format (JSON)
soda scan -c config.yml checks.yml --output json > soda-report.json

# Integration in GitHub Actions
- name: Run Soda quality checks
  run: |
    uv pip install soda-core-duckdb
    soda scan -c config.yml soda-checks.yml
    if [ $? -ne 0 ]; then
      echo "Data quality checks failed"
      exit 1
    fi
```

---

#### DQOps

**When to Use**:

- Need comprehensive observability dashboard
- Team wants minimal code
- Cloud-based deployment preferred
- Serverless data quality monitoring

**Strengths**:

```
✅ Cloud SaaS (no infrastructure)
✅ Comprehensive dashboard
✅ Automatic data profiling
✅ Schema change detection built-in
✅ Anomaly detection with ML
✅ Multi-tenant support
```

**Weaknesses**:

```
❌ Not suitable for GitHub Actions (cloud-only)
❌ Pricing not transparent
❌ Limited OSS option
❌ Requires registration/API keys
```

**Integration Complexity**: 7/10 (Cloud setup required)

**Not Recommended** for binance-futures (cloud-only, can't integrate into self-hosted workflow)

---

### Recommendation for Binance Project

**Phased Approach**:

**Phase 1**: Soda Core (Start ASAP)

- YAML-based, quick implementation
- Fits perfectly in GitHub Actions workflow
- Handles 80% of use cases (freshness, volume, validity)

**Phase 2**: Add Great Expectations (If needed later)

- Statistical anomaly detection
- Complex custom logic
- Beautiful compliance documentation

**Example Hybrid Integration**:

```yaml
# GitHub Actions workflow

- name: Run data quality checks (Soda)
  run: soda scan -c config.yml soda-checks.yml

- name: Run advanced validation (Great Expectations)
  run: uv run python scripts/validation/run_expectations.py

- name: Generate data quality report
  run: |
    python scripts/generate_quality_report.py \
      --soda-report soda-report.json \
      --gx-report gx-report.html
```

---

## 2. SLO Monitoring & Alerting Tools

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│           Binance Futures Availability Database          │
│          (GitHub Actions Workflow - daily 3AM UTC)       │
└───────────────┬─────────────────────────────────────────┘
                │
                ├─→ Collect Metrics
                │   - Workflow success/failure
                │   - Validation pass/fail
                │   - Cross-check match %
                │   - Symbol count
                │
                ├─→ Send to Monitoring Tool
                │   Option 1: Prometheus + Grafana
                │   Option 2: Grafana Cloud
                │   Option 3: Datadog (expensive)
                │
                ├─→ Store Time-Series Data
                │
                ├─→ Visualize in Dashboards
                │
                └─→ Alert on SLO Breach
                    - Slack notification
                    - Email alert
                    - PagerDuty incident
```

### Tool Comparison Matrix

| Aspect             | Prometheus + Grafana | Grafana Cloud  | Datadog       | New Relic     |
| ------------------ | -------------------- | -------------- | ------------- | ------------- |
| **Setup Time**     | 2-4 hours            | 30 min         | 1 hour        | 1 hour        |
| **Cost**           | $0-200/month (infra) | $19-299/month  | $50-500/month | $30-300/month |
| **SLO Tracking**   | Requires config      | Built-in       | Built-in      | Built-in      |
| **GitHub Actions** | Needs exporter       | Native API     | SDK available | SDK available |
| **Data Retention** | Configurable         | Unlimited      | 15 months     | 13 months     |
| **Alerting**       | Alert Manager        | Grafana Alerts | Monitors      | Conditions    |
| **Ease of Use**    | 7/10                 | 8/10           | 9/10          | 8/10          |
| **Learning Curve** | Steep                | Gentle         | Gentle        | Gentle        |
| **Vendor Lock-in** | None                 | Medium         | High          | High          |

### Detailed Comparison

#### 1. Prometheus + Grafana (Self-Hosted)

**Architecture**:

```
GitHub Actions
    ↓ (curl/push metrics)
Prometheus (time-series database)
    ↓
Grafana (visualization)
    ↓
Alert Manager → Slack/Email
```

**Setup Example**:

```yaml
# prometheus.yml
global:
  scrape_interval: 1m
  evaluation_interval: 1m

# Push from GitHub Actions via curl
# (Prometheus Pushgateway required for job-based metrics)

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

rule_files:
  - "slo_rules.yml"
```

```yaml
# slo_rules.yml (SLO definitions)
groups:
  - name: binance_futures_slos
    rules:
      # SLO 1: Availability ≥95%
      - alert: AvailabilitySLOBreach
        expr: |
          (
            sum(rate(workflow_run{status="success"}[7d]))
            /
            sum(rate(workflow_run[7d]))
          ) < 0.95
        for: 1d
        labels:
          severity: critical
        annotations:
          summary: "Availability SLO breach"

      # SLO 2: Correctness >95%
      - alert: CorrectnessSLOBreach
        expr: |
          validation_cross_check{match_percentage} < 95
        for: 1d
        labels:
          severity: critical
```

**Pros**:

```
✅ Maximum flexibility
✅ No vendor lock-in
✅ Unlimited data retention
✅ Can integrate with existing monitoring
✅ Open source
```

**Cons**:

```
❌ Requires DevOps expertise
❌ Self-hosted needs HA/backup setup
❌ Steep learning curve
❌ Need Pushgateway for GitHub Actions (extra component)
```

**Cost Breakdown**:

- Prometheus: Free (OSS)
- Grafana: Free (OSS)
- Infrastructure: $50-200/month (small VM)
- Total: $50-200/month

**Best For**: Organizations with existing Prometheus stack, strong DevOps team

---

#### 2. Grafana Cloud (SaaS)

**Architecture**:

```
GitHub Actions
    ↓ (Grafana API)
Grafana Cloud (managed SaaS)
    ├─ Prometheus (managed)
    ├─ SLO module
    └─ Alerting
    ↓
Slack / Email / PagerDuty
```

**Setup Steps**:

```bash
# 1. Sign up for Grafana Cloud (free tier available)
# 2. Get API token
# 3. Create Prometheus data source
# 4. Add metrics from GitHub Actions
# 5. Define SLOs
# 6. Configure alerts
```

**GitHub Actions Integration**:

```yaml
# .github/workflows/publish-metrics.yml

- name: Publish metrics to Grafana Cloud
  env:
    GRAFANA_URL: https://prometheus-blocks-prod-us-central1.grafana.net
    GRAFANA_TOKEN: ${{ secrets.GRAFANA_API_TOKEN }}
  run: |
    # Create metric for workflow status
    TIMESTAMP=$(date +%s)000
    STATUS="${{ job.status }}"
    VALUE=$([ "$STATUS" = "success" ] && echo 1 || echo 0)

    curl -X POST $GRAFANA_URL/api/v1/push \
      -H "Authorization: Bearer $GRAFANA_TOKEN" \
      -d "workflow_run{status=\"$STATUS\"} $VALUE $TIMESTAMP"
```

**SLO Dashboard Configuration**:

```json
{
  "slos": [
    {
      "name": "daily_update_availability",
      "target": 0.95,
      "window": "30d",
      "indicator": {
        "type": "ratio",
        "numerator": "workflow_run{status='success'}",
        "denominator": "workflow_run"
      }
    },
    {
      "name": "data_correctness",
      "target": 0.95,
      "indicator": {
        "type": "gauge",
        "metric": "validation_cross_check_match_pct"
      }
    }
  ]
}
```

**Pricing** (2025):

```
Free tier:    3 active metrics, limited retention
Pro:          $19/month (10k metrics, 50GB logs)
Advanced:     $99/month
Enterprise:   $299+/month
```

**Pros**:

```
✅ No infrastructure management
✅ Built-in SLO module
✅ 99.9% uptime SLA
✅ Easy setup (30 min)
✅ Native Slack integration
✅ No data retention limits
```

**Cons**:

```
❌ $19-99/month cost
❌ Vendor lock-in
❌ Some features in higher tiers
```

**Cost Breakdown**:

- Grafana Cloud Pro: $19/month
- Total: $228/year

**Best For**: binance-futures project (balanced cost/value)

---

#### 3. Datadog

**NOT RECOMMENDED** for binance-futures

**Reason**: Overkill + expensive

**Pricing** (typical scenario):

```
Infrastructure monitoring:  $15/host/month
Log ingestion:             $0.10-0.50/GB
Logs indexed:              $1.70/million events
APM:                       $40-200/month
Total:                     $50-500/month (easily)
```

**Example Real Cost**:

- 20 hosts: $300/month
- 100GB logs/month: $10-50/month
- Log indexing: $17/month
- APM: $100/month
- **Total**: $427/month = **$5,124/year**

**Pros**:

```
✅ All-in-one platform
✅ Excellent integrations
✅ AI-powered features
```

**Cons**:

```
❌ Expensive for single database
❌ Vendor lock-in
❌ Complex pricing
❌ Over-engineered for binance-futures
```

**Verdict**: Use Datadog only if organization already uses it company-wide

---

### Recommendation for Binance Project

**Winner: Grafana Cloud Pro ($19/month)**

**Why**:

1. **Cost**: $228/year is reasonable
2. **Setup**: 30 min vs 2-4 hours for self-hosted
3. **Features**: Built-in SLO tracking, not Prometheus add-on
4. **Reliability**: 99.9% SLA vs self-hosted uncertainty
5. **Alerting**: Native Slack integration
6. **Data Retention**: Unlimited vs 15 days (Prometheus default)

**Phase 2 Implementation**:

```yaml
# Step 1: Sign up for Grafana Cloud Pro
# Step 2: Create API token
# Step 3: Add to GitHub secrets (GRAFANA_API_TOKEN)
# Step 4: Update workflow to push metrics
# Step 5: Create SLO dashboard
# Step 6: Set up Slack alerts
```

**Monthly Costs**:

- Grafana Cloud Pro: $19
- Slack integration: $0 (built-in)
- Total: $19/month

---

## 3. Data Lineage & Catalog Tools

### Tool Comparison

| Tool                 | Setup | Cost   | Complexity | Best For                     |
| -------------------- | ----- | ------ | ---------- | ---------------------------- |
| **Markdown Catalog** | 4h    | $0     | Low        | Single DB, simple lineage    |
| **Marquez**          | 16h   | $0     | High       | Detailed job/dataset lineage |
| **DataHub**          | 20h   | $0-500 | High       | Enterprise governance        |
| **Amundsen**         | 12h   | $0     | Medium     | Search-first discovery       |

### Recommendation for Binance Project

**Use Markdown Catalog** (Section 9.4 in main report)

**Why**:

- Version-controlled (git history)
- Human + tool-readable
- No additional infrastructure
- Sufficient for single database
- Can evolve to Marquez/DataHub later if needed

**File Structure**:

```
docs/
├── schema/
│   ├── availability-database.schema.json (existing)
│   ├── query-patterns.schema.json (existing)
│   └── DATA_CATALOG.md (new)
├── lineage/
│   ├── data-flow.md (new)
│   └── impact-matrix.md (new)
└── operations/
    ├── MONITORING.md (existing)
    └── CATALOG.md (new, links everything)
```

---

## 4. Cost Summary

### Phase 0: Foundation (No Cost)

| Item                    | Cost   | Time    |
| ----------------------- | ------ | ------- |
| Schema drift detection  | $0     | 4h      |
| Batch correlation IDs   | $0     | 3h      |
| Data catalog (Markdown) | $0     | 5h      |
| **Total**               | **$0** | **12h** |

### Phase 1: SLO Monitoring (Low Cost)

| Item                   | Cost          | Time    |
| ---------------------- | ------------- | ------- |
| Grafana Cloud Pro      | $228/year     | 16h     |
| GitHub Actions metrics | $0            | 8h      |
| Dashboard setup        | $0            | 6h      |
| Slack integration      | $0            | 2h      |
| **Total**              | **$228/year** | **32h** |

### Phase 2: Data Quality (No Cost)

| Item        | Cost   | Time    |
| ----------- | ------ | ------- |
| Soda Core   | $0     | 20h     |
| Integration | $0     | 8h      |
| **Total**   | **$0** | **28h** |

### Phase 3: Advanced Validation (No Cost)

| Item               | Cost   | Time    |
| ------------------ | ------ | ------- |
| Great Expectations | $0     | 30h     |
| Custom logic       | $0     | 10h     |
| **Total**          | **$0** | **40h** |

### Overall 4-Phase Investment

```
Year 1:
  - Phase 0-3 implementation: 112 hours
  - Grafana Cloud: $228
  - Total: $228 + (112 hours × $50/hr internal) = $5,828

Year 2+:
  - Maintenance & enhancements: 20 hours/year
  - Grafana Cloud: $228/year
  - Total: $228 + $1,000 = $1,228/year
```

**ROI**: Prevents 1 major data quality incident (cost: >$10k in lost trust + manual recovery)

---

## 5. Implementation Timeline

```
┌─────────────────────────────────────────────────────────┐
│                    2025-2026 Roadmap                     │
└─────────────────────────────────────────────────────────┘

NOW (11/2025)
└─ Phase 0: Foundation
   ├─ Schema drift detection (4h)
   ├─ Batch correlation IDs (3h)
   ├─ Data catalog (5h)
   └─ Test & release (2h)
      Effort: 12h | Cost: $0

Q1 2026 (Jan-Mar)
└─ Phase 1: SLO Monitoring
   ├─ Grafana Cloud setup (4h)
   ├─ Metrics collection (8h)
   ├─ Dashboard design (6h)
   ├─ Slack alerts (2h)
   └─ Test & launch (2h)
      Effort: 32h | Cost: $228/year

Q2 2026 (Apr-Jun)
└─ Phase 2: Data Quality (Soda)
   ├─ Soda Core setup (4h)
   ├─ Write checks (10h)
   ├─ Workflow integration (6h)
   ├─ Monitoring dashboard (4h)
   └─ Test & launch (4h)
      Effort: 28h | Cost: $0

Q3 2026 (Jul-Sep)
└─ Phase 3: Advanced Validation (GX)
   ├─ GX integration (8h)
   ├─ Custom expectations (20h)
   ├─ Data Docs generation (6h)
   ├─ Compliance setup (4h)
   └─ Test & launch (2h)
      Effort: 40h | Cost: $0

TOTAL YEAR 1: 112 hours + $228 = ~$6k internal investment
```

---

## Conclusion

### Quick Decision Matrix

**Choose Soda if**: You want quick implementation, team knows SQL, need freshness/volume checks
**Choose Great Expectations if**: You need complex logic, Python expertise available, want Data Docs

**Choose Grafana Cloud if**: Want SLO tracking, managed service, $19/month acceptable
**Choose Prometheus if**: Existing monitoring stack, DevOps team available, unlimited budget for infrastructure

**Choose Markdown Catalog if**: Single database, don't need governance, want simplicity
**Choose Marquez/DataHub if**: Multiple pipelines, compliance requirements, team size >10

### For Binance Futures Availability

**Recommended Stack**:

1. **Phase 0**: DuckDB schema drift + Markdown catalog
2. **Phase 1**: Grafana Cloud Pro ($19/month)
3. **Phase 2**: Soda Core (free)
4. **Phase 3+**: Great Expectations if needed

**Expected Investment**: 112 hours + $228/year

**Expected Benefit**: Never ship bad data, catch anomalies automatically, visible SLO compliance
