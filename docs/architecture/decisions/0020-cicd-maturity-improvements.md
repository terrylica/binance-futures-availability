# ADR-0020: CI/CD Maturity Improvements

**Status**: Accepted

**Date**: 2025-11-20

**Deciders**: Automation Engineer, System Architect

**Technical Story**: Implement CI/CD Phase 1 Quick Wins (test gates, Dependabot, linting, coverage thresholds) to improve workflow maturity from 7.1/10 to 7.8/10 in 3-4 hours with 10:1 ROI.

## Context and Problem Statement

Current CI/CD infrastructure (established in ADR-0009):

- **GitHub Actions**: Production-ready with daily automation at 3AM UTC
- **Testing**: 80%+ coverage, but tests run **after** database publish
- **Dependencies**: Manual updates, no automation
- **Code Quality**: Local ruff configured, but not enforced in CI
- **Workflow Health**: No automated dependency updates, no badges

CI/CD Audit identified **8 critical gaps** with prioritized fixes:

**P0 Gaps** (prevent bad releases):

1. Tests run **after** database publish (should be before)
2. No coverage threshold enforcement (should block PRs if <80%)

**P1 Gaps** (maintenance debt): 3. No automated dependency updates (Dependabot missing) 4. No code quality gates in CI (ruff checks skipped) 5. Unused workflow file cluttering repository

**P2 Gaps** (visibility): 6. No workflow status badges in README 7. No required status checks configured

Current maturity: **7.1/10**. Path to **8.5/10 identified** across 4 phases.

## Decision Drivers

- **Maintainability SLO**: Prevent bad releases via test gates, reduce manual dependency updates
- **Correctness SLO**: Code quality gates catch regressions before merge
- **Observability SLO**: Workflow badges provide real-time visibility
- **Availability SLO**: Dependabot patches reduce vulnerability exposure
- **High ROI**: P0/P1 items have **10:1 payoff ratio** (audit report metric)
- **Low Risk**: All changes backward-compatible, no breaking changes

## Considered Options

### Option 1: Status Quo (7.1/10 Maturity)

Keep current CI/CD without improvements.

**Pros**:

- No effort required
- Existing workflows functional

**Cons**:

- **Bad releases possible**: Tests run after publish (can't block)
- **Manual dependency updates**: 2 hours/month maintenance burden
- **Code quality drift**: No linting enforcement
- **Visibility gaps**: No badges, manual health checks

### Option 2: Phase 1 Quick Wins (CHOSEN)

Implement P0/P1 improvements in 3-4 hours:

1. **Move tests before database publish** (30 min)
   - Prevents bad releases from reaching production
   - Tests block workflow if coverage <80%

2. **Add Dependabot workflow** (30 min)
   - Automated weekly dependency PRs
   - Security patches auto-detected

3. **Add ruff linting to CI** (15 min)
   - Enforces code style before merge
   - Catches common errors (unused imports, etc.)

4. **Enforce coverage threshold** (5 min)
   - Add `--cov-fail-under=80` to pyproject.toml
   - CI blocks if coverage drops

5. **Remove unused workflow** (5 min)
   - Delete `update-database-simple.yml` (20 lines, no functionality)

6. **Add workflow badges** (15 min)
   - README shows CI status at-a-glance

**Maturity Improvement**: 7.1 → **7.8** (+10%)

**Pros**:

- **High ROI**: 10:1 payoff (audit report validation)
- **Prevents Bad Releases**: Tests block publish
- **Reduces Manual Work**: Dependabot saves 24 hours/year
- **Improves Visibility**: Badges show health at-a-glance
- **Low Risk**: All changes backward-compatible

**Cons**:

- 3-4 hours implementation effort
- Stricter gates may slow down prototyping (mitigated: use feature branches)

### Option 3: Comprehensive (All 4 Phases to 8.5/10)

Implement everything: P0+P1+P2+P3 (11 hours total).

**Includes**: E2E tests in CI, CodeQL scanning, SBOM, job matrices, performance tracking.

**Pros**:

- Maximum maturity improvement

**Cons**:

- **11 hours effort** vs 3-4 hours for Phase 1
- **Diminishing Returns**: Phase 2+ has lower ROI (4:1 vs 10:1)
- **Overkill**: Phase 1 addresses critical gaps, rest can wait

### Option 4: Security Focus Only (Phase 3 Hardening)

Implement CodeQL scanning + SBOM only.

**Pros**:

- Proactive security posture

**Cons**:

- **Misses Critical Gaps**: Tests still run after publish
- **Wrong Priority**: No current vulnerabilities, but bad releases possible now

## Decision Outcome

**Chosen option**: **Option 2: Phase 1 Quick Wins**

### Rationale

1. **Addresses Critical Gaps First**: P0 items prevent bad releases (**highest impact**)
2. **High ROI**: 10:1 payoff ratio for 3-4 hours work (audit report validation)
3. **Maintainability**: Dependabot saves 24 hours/year manual dependency updates
4. **Low Risk**: All changes backward-compatible, full rollback available
5. **Foundation**: Phase 1 enables Phase 2+ (test gates required before adding E2E tests)

**Deferred to Future**:

- **Phase 2** (Q1 2026): E2E tests in CI, CodeCov integration
- **Phase 3** (Q2 2026): CodeQL scanning, SBOM generation
- **Phase 4** (Later 2026): Job matrices, performance tracking

### Implementation Strategy

**Task 1: Move Tests Before Database Publish** (30 min)

**File**: `.github/workflows/update-database.yml`

```yaml
# Current (WRONG): Tests run after publish (line 358)
steps:
  - name: Update database
  - name: Validate database
  - name: Publish to GitHub Releases    # Line 450
  - name: Run tests                      # Line 358 (TOO LATE)

# Fixed (CORRECT): Tests run before publish
steps:
  - name: Setup environment
  - name: Run tests                      # MOVED HERE
  - name: Run linting                    # NEW
  - name: Update database                # Only if tests pass
  - name: Validate database
  - name: Publish to GitHub Releases     # Only if validation passes
```

**Task 2: Create Dependabot Configuration** (30 min)

**File**: `.github/dependabot.yml` (NEW)

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    allow:
      - dependency-type: "all"
    reviewers:
      - "terrylica"

  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    allow:
      - dependency-type: "all"
```

**Task 3: Add Ruff Linting to CI** (15 min)

**File**: `.github/workflows/update-database.yml`

```yaml
- name: Lint code
  run: ruff check src/ tests/
```

**Task 4: Enforce Coverage Threshold** (5 min)

**File**: `pyproject.toml`

```toml
[tool.pytest.ini_options]
addopts = ["--cov-fail-under=80"]
```

**Task 5: Remove Unused Workflow** (5 min)

```bash
git rm .github/workflows/update-database-simple.yml
```

**Task 6: Add Workflow Badges** (15 min)

**File**: `README.md`

```markdown
# Binance Futures Availability Database

[![Daily Update](https://github.com/terrylica/binance-futures-availability/workflows/Update%20Binance%20Futures%20Availability%20Database/badge.svg)](https://github.com/terrylica/binance-futures-availability/actions/workflows/update-database.yml)
[![Release](https://github.com/terrylica/binance-futures-availability/workflows/Release/badge.svg)](https://github.com/terrylica/binance-futures-availability/actions/workflows/release.yml)
```

### Validation Criteria

✅ Tests run **before** database publish in workflow
✅ Workflow fails if tests fail
✅ Workflow fails if coverage <80%
✅ Dependabot creates weekly PR
✅ Ruff linting runs in CI
✅ Unused workflow deleted
✅ Badges visible in README

## Consequences

### Positive

- **Prevents Bad Releases**: Tests block publish (P0 gap closed)
- **Reduces Manual Work**: Dependabot saves 24 hours/year
- **Improves Code Quality**: Linting catches errors before merge
- **Increases Visibility**: Badges show health at-a-glance
- **Foundation for Phase 2**: Test gates enable E2E test integration
- **Maturity Improvement**: 7.1 → 7.8 (+10%)

### Negative

- **Stricter Gates**: Prototyping may need feature branches
- **Dependabot Noise**: Weekly PRs require review (mitigated: auto-merge patch versions)
- **Initial Setup**: 3-4 hours implementation

### Neutral

- **Workflow Count**: Same (1 deleted, 1 added via Dependabot config)
- **Test Runtime**: Unchanged (tests already run, just earlier in pipeline)

## Compliance

### SLOs Addressed

- ✅ **Availability**: Dependabot security patches reduce vulnerability-related downtime
- ✅ **Correctness**: Test gates prevent bad releases, linting catches errors
- ✅ **Observability**: Badges provide real-time workflow health visibility
- ✅ **Maintainability**: Automated updates reduce manual work from 2h/month → 0.5h/month

### Error Handling

All CI/CD changes follow ADR-0003 strict raise policy:

- ✅ Test failures abort workflow (pytest --exitfirst)
- ✅ Coverage failures abort workflow (--cov-fail-under=80)
- ✅ Lint failures abort workflow (ruff check, exit code 1)
- ✅ No silent fallbacks or default values

### Documentation Standards

- ✅ **No promotional language**: Focus on gap analysis, not "better CI/CD"
- ✅ **Abstractions over implementation**: Explain "why test gates" not "how YAML works"
- ✅ **Intent over implementation**: Document decision drivers (quality, reliability), not just commands

## Links

- **Research**: `docs/research/2025-week1-sprint/CI_CD_AUDIT_REPORT.md` (30KB, comprehensive audit)
- **Dependabot Documentation**: https://docs.github.com/en/code-security/dependabot
- **GitHub Actions Best Practices**: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions
- **Related ADRs**:
  - ADR-0009: GitHub Actions Automation (CI/CD foundation)
  - ADR-0016: Playwright E2E Testing (future Phase 2 integration)

## Implementation Notes

### Post-Deployment Incident (2025-11-21)

**Incident**: Linting gate blocked daily scheduled updates for 4 days (Nov 18-21).

**Root Cause**: Pre-existing technical debt (149 linting violations) surfaced when strict ruff gate was added. Primary culprit: `scripts/benchmark_workers.py` (6 errors from benchmarking work).

**Resolution** (Commit 76b3c3a):
1. Auto-fixed 123 violations (imports, f-strings, type hints)
2. Added strategic exceptions to `pyproject.toml` for 26 remaining violations:
   ```toml
   ignore = [
       "DTZ005",  # datetime.now() without tz - Phase 2 cleanup
       "DTZ007",  # strptime without tz - argparse validators, low risk
       "DTZ011",  # date.today() without tz - Phase 2 cleanup
       "SIM117",  # Multiple with statements - stylistic
       "PT017",   # pytest assert in except - valid pattern
   ]
   ```
3. Created monitoring infrastructure (`scripts/operations/monitor_workflow.sh` with Pushover)

**Impact**:
- MTTR: 37 minutes (detection → deployment)
- Data gap: 4 days (Nov 18-21, ~1,308 records)
- SLO breach: 0% availability vs 95% target

**Lessons Learned**:
1. ✅ **Linting gates work**: Successfully caught 149 code quality issues
2. ⚠️ **Incremental rollout needed**: Should have tested gate on feature branch
3. ✅ **Strategic exceptions valid**: Pragmatic approach to unblock critical pipeline
4. ✅ **Monitoring gap filled**: Added Pushover alerting for workflow failures

**Follow-up Actions**:
- [ ] Phase 2: Fix timezone errors (DTZ rules) - track in separate issue
- [ ] Remove strategic exceptions after Phase 2 cleanup
- [ ] Add pre-commit hooks to catch violations locally

**Execution Log**: `logs/0020-bugfix-linting-pipeline-20251121_133907.log`

## Notes

This improvement is part of Week 1-2 Sprint (comprehensive infrastructure improvements). Associated plan: `docs/development/plan/week1-2-sprint-infrastructure-upgrade/plan.md` with `adr-id=0020`.

**Maturity Tracking**: Current 7.1/10 → Phase 1: 7.8/10 → Phase 2: 8.2/10 → Phase 3: 8.5/10 (audit report roadmap).
