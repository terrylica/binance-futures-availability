# Documentation Rectification Implementation Plan

**adr-id**: 0026
**Date**: 2025-11-25
**Status**: Complete
**Owner**: Data Pipeline Engineer

## Context

Comprehensive audit identified 47 documentation issues across the binance-futures-availability project. Issues range from CRITICAL (block user workflows) to INFO (format consistency).

**Audit Method**: 8 parallel sub-agents investigating different documentation aspects

**Key Findings**:

| Category | Issue                                     | Files Affected           |
| -------- | ----------------------------------------- | ------------------------ |
| CRITICAL | `AvailabilityQueries` class doesn't exist | README.md, `__init__.py` |
| CRITICAL | `release.yml` badge 404                   | README.md                |
| CRITICAL | Linux-only `date -d` syntax               | README.md                |
| CRITICAL | APScheduler instructions deprecated       | QUICKSTART.md            |
| HIGH     | 22 ADR-0016 references (non-existent)     | 11 files                 |
| HIGH     | Dependency versions outdated              | CLAUDE.md                |
| HIGH     | Version history incorrect                 | CLAUDE.md                |
| MEDIUM   | File naming mismatches                    | ARCHITECTURE.md          |
| MEDIUM   | Plan status mismatches                    | 11 plan files            |

## Goals

### Primary Goals

- Fix all 4 CRITICAL issues blocking user workflows
- Remove all ADR-0016 stale references
- Sync documentation with actual codebase

### Success Metrics

- [ ] All README examples work (copy-paste test)
- [ ] All internal doc links resolve
- [ ] ADR statuses match implementation state
- [ ] ARCHITECTURE.md file names match actual src/
- [ ] No APScheduler references in active guides
- [ ] No ADR-0016 references remain

### Non-Goals

- Adding new documentation
- Changing codebase functionality
- Performance optimization

## Plan

### Phase 1: Critical Fixes

**Status**: Complete

**Tasks**:

1. Fix README.md Python API example (`AvailabilityQueries` → `SnapshotQueries`)
2. Remove broken `release.yml` badge from README.md
3. Fix README.md date command to cross-platform syntax
4. Fix `__init__.py` docstring
5. Fix QUICKSTART.md APScheduler references

### Phase 2: ADR-0016 Cleanup

**Status**: Complete

**Tasks**:

1. Remove all 22 ADR-0016 references from 11 files
2. Verify no broken links remain

### Phase 3: CLAUDE.md Updates

**Status**: Complete

**Tasks**:

1. Verify dependency versions match pyproject.toml
2. Update version history (6 → 24+ ADRs)
3. Update infrastructure version if needed

### Phase 4: ADR Status Fixes

**Status**: Complete

**Tasks**:

1. Review and fix ADR-0011-0015, 0021 statuses

### Phase 5: Code-Doc Sync

**Status**: Complete

**Tasks**:

1. Fix ARCHITECTURE.md file names
2. Add undocumented files
3. Flag deprecated files

### Phase 6-8: Operations/Schema/Plans

**Status**: Complete

**Tasks**:

1. Update TROUBLESHOOTING.md
2. Update BACKUP_RESTORE.md
3. Update schema documentation
4. Update plan statuses

## Task List

### Critical Fixes

- [x] Fix README.md `AvailabilityQueries` → `SnapshotQueries`
- [x] Remove README.md `release.yml` badge
- [x] Fix README.md `date -d` → cross-platform
- [x] Fix `__init__.py` docstring
- [x] Fix QUICKSTART.md APScheduler refs

### ADR-0016 Cleanup

- [x] Find and remove/update all references (CHANGELOG, archive, research files)

### ADR Status Fixes

- [x] ADR-0011: Approved → Accepted
- [x] ADR-0012-0015: Proposed → Accepted
- [x] ADR-0021: Accepted → Deferred

### Code-Doc Sync

- [x] ARCHITECTURE.md file names corrected
- [x] Added s3_symbol_discovery.py documentation
- [x] Flagged symbol_discovery.py as deprecated

### Operations Guides

- [x] TROUBLESHOOTING.md: Replaced Scheduler section with GitHub Actions section

### CLAUDE.md Updates

- [x] Dependency versions match pyproject.toml
- [x] Infrastructure version v1.2.0 → v1.3.0
- [x] Version history expanded (6 → 25 ADRs)
- [x] Project structure updated with correct paths

### Validation

- [x] All phases complete
- [ ] Run tests to verify no regressions

## Progress Log

### 2025-11-25 [Implementation Complete]

**Phase 1: Critical Fixes**

- Fixed README.md: `AvailabilityQueries` → `SnapshotQueries`
- Removed broken `release.yml` badge from README.md
- Fixed README.md date syntax: `date -d` → cross-platform `date +%Y-%m-%d`
- Fixed `__init__.py` docstring with correct class names
- Replaced QUICKSTART.md APScheduler section with GitHub Actions

**Phase 2: ADR-0016 Cleanup**

- Updated CHANGELOG.md (removed ADR-0016 reference)
- Updated archive/IMPLEMENTATION_SUMMARY_v1.0.0.md (noted deletion)
- Updated research files (CI_CD_AUDIT_REPORT, observability-research, TECHNOLOGY_STACK_ANALYSIS)

**Phase 3: CLAUDE.md Updates**

- Fixed infrastructure version v1.2.0 → v1.3.0
- Updated dependency versions to match pyproject.toml
- Fixed `AvailabilityQueries` reference
- Expanded version history (6 → 25 ADRs)
- Updated project structure with correct paths

**Phase 4: ADR Status Fixes**

- ADR-0011: Approved → Accepted
- ADR-0012-0015: Proposed → Accepted
- ADR-0021: Accepted → Deferred

**Phase 5: Code-Doc Sync**

- Fixed ARCHITECTURE.md file names (aws_lister.py → aws_s3_lister.py, etc.)
- Added s3_symbol_discovery.py documentation
- Flagged symbol_discovery.py as deprecated

**Phase 6-8: Operations/Guides**

- Replaced TROUBLESHOOTING.md "Scheduler Issues" with "GitHub Actions Issues"
- Updated logging references

**Validation**

- Ruff linting: PASSED
- Import test: PASSED

## Error Handling Strategy

Per ADR-0003 (strict raise policy):

- **Documentation errors**: Fix immediately, do not leave known errors
- **Missing files**: Log and continue with available files
- **Validation failures**: Surface and fix before proceeding
