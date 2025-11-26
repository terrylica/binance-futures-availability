# ADR-0026: Documentation Rectification

**Status**: Accepted

**Date**: 2025-11-25

**Context**:

Comprehensive audit by 8 sub-agents identified 47 documentation issues across 6 severity levels:

| Severity | Count | Impact                 |
| -------- | ----- | ---------------------- |
| CRITICAL | 4     | Block user workflows   |
| HIGH     | 12    | Documentation accuracy |
| MEDIUM   | 18    | Completeness gaps      |
| LOW      | 8     | Minor clarifications   |
| INFO     | 5     | Format consistency     |

Key issues discovered:

1. **Non-existent class**: README and `__init__.py` reference `AvailabilityQueries` which doesn't exist (actual: `SnapshotQueries`)
2. **Broken badge**: `release.yml` workflow badge links to 404 (workflow doesn't exist)
3. **Platform incompatibility**: `date -d` syntax is Linux-only (macOS users fail)
4. **Stale references**: 22 references to non-existent ADR-0016 across 11 files
5. **Deprecated instructions**: APScheduler references in QUICKSTART.md (superseded by ADR-0009)

**Decision**:

Rectify all 47 documentation issues in 8 phases:

1. **Critical Fixes**: README, QUICKSTART, `__init__.py`
2. **ADR-0016 Cleanup**: Remove all 22 stale references
3. **CLAUDE.md Updates**: Dependency versions, version history
4. **ADR Status Fixes**: Correct status inconsistencies
5. **Code-Doc Sync**: ARCHITECTURE.md alignment
6. **Operations Guides**: TROUBLESHOOTING, BACKUP_RESTORE
7. **Schema/API Docs**: Missing indexes, CLI commands
8. **Plan Status Sync**: Match implementation state

**Consequences**:

**Positive**:

- All README examples will work (copy-paste test)
- All internal doc links will resolve
- No broken badges or 404 links
- Platform-agnostic commands (macOS/Linux)
- ADR statuses match implementation state

**Negative**:

- One-time effort to audit and fix 47 issues
- May surface additional issues during implementation

**Related Decisions**:

- ADR-0003: Error handling - strict policy
- ADR-0009: GitHub Actions automation (supersedes APScheduler)
- ADR-0017: Documentation structure migration

**SLO Compliance**:

- **Availability**: Documentation accessible without 404 errors
- **Correctness**: Examples work, class names match code
- **Observability**: All changes tracked in plan document
- **Maintainability**: Consistent MADR statuses, no stale references
