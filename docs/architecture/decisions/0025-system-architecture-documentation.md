# ADR-0025: System Architecture Documentation

**Status**: Accepted

**Date**: 2025-11-25

**Context**:

The binance-futures-availability project lacks a comprehensive architectural visualization. While 4 ASCII diagrams exist scattered across documentation:

1. `docs/operations/GITHUB_ACTIONS.md` (L12-33) - CI/CD workflow pipeline
2. `docs/architecture/decisions/0012-auto-backfill-new-symbols.md` (L41-50) - Conditional workflow tree
3. `docs/guides/QUICKSTART.md` (L156-162) - File system tree
4. `docs/benchmarks/worker-count-benchmark-2025-11-15.md` (L21-30) - Performance chart

No single document provides:
- End-to-end data flow visualization (S3 → DuckDB → Distribution)
- Runtime control flow modes (scheduled vs manual vs CLI)
- Component relationships and integration points
- Deployment topology overview

**Decision**:

Create `docs/architecture/ARCHITECTURE.md` as a centralized architecture documentation with:

1. **Data Flow Architecture** - Visualize data movement from Binance S3 through collection, storage, and distribution
2. **Runtime Control Flow** - Document trigger sources and execution modes
3. **Component Architecture** - Map src/ module structure and responsibilities
4. **Deployment Topology** - Show GitHub Actions and Releases integration

All diagrams use ASCII art for universal compatibility (no external rendering tools required).

**Consequences**:

**Positive**:

- Single source of truth for architectural understanding
- ASCII diagrams render in any text editor, terminal, or markdown viewer
- Supports onboarding and code review context
- Links to detailed ADRs for decision rationale

**Negative**:

- ASCII diagrams require manual maintenance when architecture changes
- Limited visual expressiveness compared to graphical tools

**Related Decisions**:

- ADR-0002: Storage Technology - DuckDB
- ADR-0009: GitHub Actions Automation
- ADR-0010: Dynamic Symbol Discovery
- ADR-0022: Pushover Workflow Notifications

**Artifacts Created**:

- `docs/architecture/ARCHITECTURE.md` - Comprehensive architecture documentation
- `docs/development/plan/0025-system-architecture-documentation/plan.md` - Implementation plan

**SLO Compliance**:

- **Availability**: Documentation accessible in repository (no external dependencies)
- **Correctness**: Diagrams validated against actual codebase structure
- **Observability**: Cross-referenced with ADRs and CLAUDE.md
- **Maintainability**: ASCII format editable without specialized tools
