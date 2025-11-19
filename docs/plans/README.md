# DEPRECATED: Documentation Structure Migrated

**This directory is deprecated as of 2025-11-18.**

All implementation plans have been moved to:

```
docs/development/plan/
```

Please update your bookmarks and references.

## Migration Details

- **ADR-0017**: Documentation Structure Migration
- **New location**: `docs/development/plan/NNNN-slug/plan.md` or `plan.yaml`
- **Format change**: Migrating from YAML to Google Design Doc markdown format
- **Rationale**: Improve readability, enable ADR↔plan traceability via `adr-id` linkage

## Quick Reference

| Old Path                                     | New Path                                             |
| -------------------------------------------- | ---------------------------------------------------- |
| `docs/plans/v1.0.0-implementation-plan.yaml` | `docs/development/plan/v1.0.0/plan.yaml`             |
| `docs/plans/0007-trading-volume-metrics/`    | `docs/development/plan/0007-trading-volume-metrics/` |
| `docs/plans/0008-workspace-organization/`    | `docs/development/plan/0008-workspace-organization/` |
| ...                                          | ...                                                  |
| `docs/plans/0015-skill-extraction/`          | `docs/development/plan/0015-skill-extraction/`       |

## New Format Example

Plans now include explicit ADR linkage:

```markdown
---
adr-id: 0017
title: Documentation Structure Migration Plan
status: approved
---

# Documentation Structure Migration Plan

## Context

...
```

See ADR-0017 for full migration details: `docs/architecture/decisions/0017-documentation-structure-migration.md`
