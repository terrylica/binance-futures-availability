# ADR-0008: Workspace Organization and Legacy Code Management

**Status**: Implemented
**Date**: 2025-11-14
**Implemented**: 2025-11-19
**Deciders**: Terry Li, Claude Code, Cleanup Analysis Agents
**Related**: ADR-0005 (AWS CLI), ADR-0007 (Volume Metrics), ADR-0009 (GitHub Actions)

## Context

Following implementation of AWS CLI-based operations (ADR-0005) and trading volume metrics (ADR-0007), the project workspace has accumulated technical debt across multiple dimensions:

### Documentation Inconsistencies

**Script Reference Drift**: 30+ documentation references point to non-existent scripts:

- `run_backfill.py` (referenced in CLAUDE.md, IMPLEMENTATION_STATUS.md)
- `run_backfill_aws.py` (referenced in README.md, 5 other docs)
- Actual path: `scripts/operations/backfill.py`

**Content Redundancy**: 70% overlap between CLAUDE.md and README.md, 40% estimated redundancy across all docs

**Outdated Guides**: `OVERNIGHT_BACKFILL_GUIDE.md` describes deprecated 7.3-hour HEAD-based backfill (ADR-0005 replaced with 25-minute AWS CLI approach)

### Legacy Code Accumulation

**Deprecated Scripts**: `scripts/legacy/backfill_head.py` documented as obsolete but not removed

**Dual Backfill Paths**: Project maintains two approaches:

1. Fast AWS CLI (`scripts/operations/backfill.py`) - 25 minutes
2. Slow HEAD requests (`BackfillScheduler`) - 3 hours

**Architectural Confusion**: Users unsure which backfill method to use (CLI vs standalone script)

### Build Artifact Accumulation

**Temporary Files**: 67 MB of build artifacts (coverage reports, pytest cache, lychee results, `__pycache__`)

**Optional Dependencies**: 143 MB of reinstallable dependencies (node_modules 65 MB, .venv 78 MB)

**Log Files**: 289 KB of completed backfill logs

### Impact on Project Health

**Correctness Risk**: Broken documentation references lead users to execute non-existent commands

**Maintainability Burden**: 30-40% redundant documentation increases maintenance overhead

**Observability Gap**: Unclear separation between active code, deprecated code, and temporary artifacts

**Onboarding Friction**: New developers confused by outdated guides and dual implementation paths

## Decision

Implement systematic workspace organization with formal tracking and validation:

### 1. Documentation Hygiene Policy

**Single Source of Truth Hierarchy**:

- CLAUDE.md: Comprehensive developer reference (AI context)
- README.md: High-level user overview with links
- docs/guides/: User-facing tutorials
- docs/operations/: Operational runbooks

**Script Reference Standardization**:

- All documentation must reference `scripts/operations/backfill.py` (not legacy aliases)
- Automated validation via link checker + grep verification
- References to deprecated scripts only allowed in ADR historical context

**Redundancy Elimination**:

- Remove duplicate installation instructions (keep in QUICKSTART.md only)
- Remove duplicate schema definitions (CLAUDE.md is SSoT, README links to schema.json)
- Consolidate troubleshooting (TROUBLESHOOTING.md is SSoT)

### 2. Legacy Code Deprecation Path

**Safe Deletion Criteria**:

1. Script explicitly documented as deprecated in `scripts/legacy/README.md`
2. No active imports found via `grep -r "import.*filename"`
3. Replaced by newer implementation with ADR rationale

**Deprecation Process**:

1. Move deprecated scripts to `scripts/legacy/`
2. Document replacement in `scripts/legacy/README.md`
3. Update all documentation references
4. After 1 release cycle, remove deprecated script

**Keep Legacy for Daily Operations**:

- Retain `s3_vision.py` and `batch_prober.py` (HEAD-based probing still optimal for daily updates per ADR-0005)
- Document hybrid strategy prominently (AWS CLI for bulk, HEAD for incremental)

### 3. Build Artifact Retention Policy

**Safe to Delete (Regenerable)**:

- Coverage reports (`.coverage`, `htmlcov/`)
- Pytest cache (`.pytest_cache/`)
- Python bytecode (`__pycache__/`, `*.pyc`)
- Lychee link checker cache (`.lychee*`)
- Completed backfill logs (archive to `~/.cache/binance-futures/logs/archive/`)

**Safe to Remove (Reinstallable)**:

- Node.js dependencies (`node_modules/`, `package-lock.json`)
- Python venv (`.venv/`)

**Never Remove**:

- Production database (`~/.cache/binance-futures/availability.duckdb`)
- Active logs (`volume_backfill_overnight.log` if process running)
- Checkpoint files (`backfill_checkpoint.txt`)

### 4. Documentation Archive Policy

**Archive Criteria**:

- Document describes one-time operation that is complete
- Content is outdated but has historical value
- Keeping in main docs would confuse users

**Archive Process**:

1. Move to `docs/archive/FILENAME_YYYY-MM-DD.md`
2. Add archive notice to top of file with date and reason
3. Update references in active docs to point to replacement

**Candidates for Archiving**:

- `IMPLEMENTATION_STATUS.md` → `docs/archive/IMPLEMENTATION_STATUS_v1.0.0.md`
- `OVERNIGHT_BACKFILL_GUIDE.md` → DELETE (severely outdated, misleading)

## Rationale

### Correctness

**Problem**: 30+ broken script references across 6 documentation files

**Solution**: Automated validation + systematic reference updates

**Measurement**: `grep -r "scripts/" docs/ | verify_script_paths.sh` returns 0 errors

### Maintainability

**Problem**: 40% documentation redundancy increases maintenance cost (every update requires 3-4 file changes)

**Solution**: Single Source of Truth hierarchy with clear linking strategy

**Measurement**: Redundancy reduced from 40% to <10% (measured via diff analysis)

### Observability

**Problem**: Unclear separation between active code, deprecated code, temporary artifacts

**Solution**: Formal directory structure (`scripts/operations/` vs `scripts/legacy/`) + retention policies

**Measurement**: `tree scripts/` output shows clear organization, zero confusion about what's active

### Availability

**Problem**: Risk of accidentally removing code needed for daily automation

**Solution**: Explicit keep list for HEAD-based probing modules per ADR-0005

**Measurement**: Daily scheduler continues running post-cleanup (validated with `ps aux | grep scheduler`)

## Consequences

### Positive

**Correctness Improvement**: Zero broken documentation references (down from 30+)

**Maintainability Improvement**:

- 25% less documentation content to maintain
- Clear SSoT hierarchy reduces update overhead from 3-4 files to 1 file

**Observability Improvement**:

- Clear directory structure (operations vs legacy)
- Formal retention policies documented
- New developers onboard 30% faster (estimated)

**Disk Space Reclaimed**: 68 MB (145 MB if removing node_modules + venv)

### Negative

**One-Time Migration Effort**:

- 6 documentation files need updates
- ~2 hours of manual editing + validation

**Potential Regression Risk**:

- Might miss some script references during grep
- Mitigation: Automated link checker + test suite validation

**Archive Policy Maintenance**:

- Need to remember to archive docs for future one-time operations
- Mitigation: Add to CONTRIBUTING.md checklist

### Neutral

**No Performance Impact**: Workspace organization is developer-facing only

**No API Changes**: Public interfaces unchanged

**No Database Changes**: Production data untouched

## Implementation

See implementation plan: `docs/plans/0008-workspace-organization/plan.yaml`

**Phases**:

1. Remove safe build artifacts
2. Fix documentation script references
3. Archive outdated guides
4. Validate with link checker + test suite

**Success Criteria**:

- Zero broken documentation links
- All script references point to existing files
- <10% content redundancy
- Test suite passes (no broken imports)
- Daily scheduler unaffected

## References

**Analysis Reports**:

- Legacy code analysis: `/tmp/workspace-cleanup/legacy-code-analysis.md`
- Documentation redundancy: `/tmp/workspace-cleanup/docs-redundancy-analysis.md`
- Data cache analysis: `/tmp/workspace-cleanup/data-cache-analysis.md`
- Temporary files analysis: `/tmp/workspace-cleanup/temp-files-analysis.md`

**Related ADRs**:

- ADR-0005: AWS CLI bulk operations (explains HEAD vs AWS CLI strategy)
- ADR-0007: Trading volume metrics (context for recent script changes)

**External References**:

- Binance Vision S3 structure: https://data.binance.vision/
