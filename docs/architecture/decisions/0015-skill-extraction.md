# ADR-0015: Extract Validated Workflows into Atomic Skills

**Status**: Accepted
**Date**: 2025-11-17
**Deciders**: Development Team
**Related**: [ADR-0013: Volume Rankings Archive](0013-volume-rankings-timeseries.md), [ADR-0014: Easy Query Access](0014-easy-query-access.md)

## Context

During implementation of ADR-0013 (Volume Rankings) and ADR-0014 (Easy Query Access), we developed and validated three distinct workflows that proved effective and reusable:

1. **Multi-Agent Parallel Investigation**: Spawned 4 parallel sub-agents with different perspectives (GitHub API capabilities, remote query validation, documentation assessment, CLI tool feasibility) to investigate "Can users query rankings easily?" - each using dynamic writeTodo creation
2. **Remote Parquet Query Pattern**: Discovered DuckDB HTTP reads enable zero-download queries from GitHub Releases using range requests (1-3 second performance, column/row pruning)
3. **Documentation Improvement Workflow**: Systematic transformation from "comprehensive reference" (7.5/10) to "approachable quick-start + reference" (9/10) by adding Quick Start, Prerequisites, Remote Examples, fixing URL placeholders

**Problem**: These validated patterns are embedded in session context but not captured as reusable artifacts for future projects.

**Investigation Findings** (3 parallel sub-agents, 2025-11-17):

**Agent 1 (Skills Architecture Analyst)**:

- Analyzed 22 existing skills in `~/.claude/skills/`
- Identified canonical structure: SKILL.md (YAML frontmatter + instructions) + references/scripts/assets
- Found 2 relevant multi-agent skills: `multi-agent-e2e-validation`, `multi-agent-performance-profiling`
- Recommended naming: `multi-agent-parallel-investigation`, `duckdb-remote-parquet-query`, `documentation-improvement-workflow`

**Agent 2 (Skill Design Specialist)**:

- Extracted core reusable patterns from ADR-0013/0014 workflows
- Designed 3 complete specifications (Purpose, Inputs, Outputs, Workflow, Tools, Domain Context)
- Validated against crypto/trading data analysis workflows
- Confirmed domain-specific but generic (no ADR references in skill content)

**Agent 3 (CLAUDE.md Structure Analyst)**:

- Current CLAUDE.md has no skills section
- Recommended insertion: After "Related Projects" (line 296), before "SSoT Documentation"
- Link Farm format: H3 heading + one-liner description
- Hub-and-Spoke: CLAUDE.md = hub, skills/\*.md = spokes

**User Requirements**:

- Extract 3 workflows: Multi-agent investigation, Remote Parquet query, Documentation improvement
- Domain-specific skills (crypto/trading context)
- Generic/abstract (no specific ADR-0013/0014 references)
- Update CLAUDE.md as Link Farm with progressive disclosure

## Decision

Create 3 atomic, domain-specific skills under `./skills/` directory and update CLAUDE.md with Reusable Skills section following Link Farm pattern.

### Skill 1: multi-agent-parallel-investigation

**Purpose**: Decompose complex questions into 4-6 parallel investigations with different specialist perspectives, synthesize findings into phased decision framework.

**When to Use**: Architecture decisions with multiple unknowns requiring diverse expertise (e.g., storage technology selection, query optimization strategy, tooling choices).

**Domain Context**: Data platform decisions in crypto/trading projects where technical trade-offs span multiple dimensions (performance, cost, developer experience, infrastructure).

**Core Workflow**:

1. Define investigation question and success criteria
2. Identify 4-6 specialist perspectives (API capabilities, performance, documentation, feasibility)
3. Spawn parallel sub-agents with role-specific prompts and dynamic writeTodo creation
4. Collect structured reports from each agent (findings, recommendations, confidence levels)
5. Synthesize into phased decision framework with prioritized options

**Tools Required**: Claude Task tool, writeTodo tracking, structured reporting templates

### Skill 2: duckdb-remote-parquet-query

**Purpose**: Query remote Parquet files on HTTP storage (S3, GitHub Releases, etc.) without downloading, using DuckDB httpfs extension with HTTP range requests for efficient column/row pruning.

**When to Use**: Large columnar datasets on remote storage requiring exploratory queries, cost-sensitive analysis (avoid egress fees), or environments with limited local storage.

**Domain Context**: Crypto/trading data archives (OHLCV, volume rankings, exchange metadata, funding rates) where datasets are large (>100 MB) but queries are selective.

**Core Workflow**:

1. Identify remote Parquet file URL (GitHub Releases, S3, HTTP endpoint)
2. Configure DuckDB with httpfs extension (auto-loaded in modern versions)
3. Write query with WHERE filters for predicate pushdown (minimize data transfer)
4. Select specific columns for column pruning (not SELECT \*)
5. Measure performance and compare to local file if needed

**Tools Required**: DuckDB >=1.0.0, httpfs extension, Parquet files on HTTP-accessible storage

### Skill 3: documentation-improvement-workflow

**Purpose**: Transform comprehensive reference documentation into approachable quick-start structure by adding Quick Start section, Prerequisites, practical examples, and fixing placeholder URLs.

**When to Use**: Documentation receives feedback about complexity, onboarding friction, or when assessment shows "technically excellent but poor onboarding" (rating <8/10).

**Domain Context**: Dataset guides, API integration docs, backtest setup, pipeline configuration in crypto/trading projects where developer audience needs fast time-to-first-query.

**Core Workflow**:

1. Assess current documentation (identify gaps: no Quick Start, missing Prerequisites, placeholder URLs)
2. Add Quick Start section (copy-paste example, <60 seconds to results, hardcoded values)
3. Add Prerequisites section (Python version, installation commands, library versions)
4. Add practical examples (remote queries, common use cases, performance tips)
5. Fix placeholder URLs (replace YOUR_USERNAME with actual paths or env vars)
6. Measure improvement (before/after rating, time-to-first-query)

**Tools Required**: Documentation analysis checklist, quick-start templates, assessment rubric

### CLAUDE.md Update

Add "Reusable Skills" section after "Related Projects", before "SSoT Documentation":

```markdown
## Reusable Skills

Domain-specific skills extracted from this project for reuse across workspaces:

### [Multi-Agent Parallel Investigation](skills/multi-agent-parallel-investigation/SKILL.md)

Decompose complex questions into 4-6 parallel investigations with different perspectives, synthesize into phased decision framework

### [DuckDB Remote Parquet Query](skills/duckdb-remote-parquet-query/SKILL.md)

Query Parquet files on remote storage without downloading using DuckDB's httpfs extension with HTTP range requests

### [Documentation Improvement Workflow](skills/documentation-improvement-workflow/SKILL.md)

Transform reference docs into quick-start structure by adding Quick Start, Prerequisites, and practical examples
```

## Consequences

### Positive

**Reusability**:

- ✅ Validated workflows become reusable across projects (not lost in session context)
- ✅ Future crypto/trading data projects can invoke skills directly
- ✅ Progressive disclosure via CLAUDE.md Link Farm (Hub-and-Spoke)
- ✅ Domain-specific optimizations preserved (crypto data characteristics)

**Knowledge Capture**:

- ✅ Investigation patterns documented (4-6 parallel agents, dynamic writeTodo)
- ✅ Technical solutions captured (DuckDB HTTP range requests, performance characteristics)
- ✅ Documentation transformation patterns standardized (7.5/10 → 9/10 improvements)

**Maintainability**:

- ✅ Skills follow canonical structure (SKILL.md + references/ + scripts/)
- ✅ Generic/abstract (no ADR references - won't become outdated)
- ✅ OSS tool dependencies (DuckDB, Claude Task tool, markdown templates)
- ✅ Validation via `quick_validate.py`

### Negative

**Abstraction Challenges**:

- ⚠️ Generic skills may lose context-specific nuances from ADR-0013/0014
- ⚠️ Domain-specific focus limits applicability outside crypto/trading
- ⚠️ No concrete examples in SKILL.md (must reference external docs)

**Maintenance Overhead**:

- ⚠️ 3 new skills to maintain (updates when tools/patterns evolve)
- ⚠️ CLAUDE.md Link Farm grows (currently 3 skills, could expand)
- ⚠️ Skill invocation requires user awareness (not automatic)

### Neutral

**Trade-offs**:

- Skills provide methodology but require user judgment for application
- Domain-specific focus trades broad applicability for crypto/trading optimization
- Progressive disclosure requires 2 clicks (CLAUDE.md → SKILL.md → references/)

## SLO Alignment

**Availability**: N/A (skills are documentation, not runtime components)

**Correctness**: 100% (skills extracted from validated workflows in ADR-0013/0014, empirically tested)

**Observability**: N/A (skills don't generate telemetry, user observes skill invocation results)

**Maintainability**:

- Skill updates: <1 hour per skill for minor changes
- Follows canonical structure (22 existing skills as references)
- Generic/abstract content stable (no ADR coupling)
- Validation via `quick_validate.py` catches structural errors

## Implementation

**Phases**:

1. Create 3 skills via `skill-architecture` skill invocation (3-5 hours)
2. Update CLAUDE.md with Link Farm section (30 minutes)
3. Validate skills and links (30 minutes)
4. Commit with conventional commits (30 minutes)

**Validation**:

- Invoke `skill-architecture` skill for each skill creation
- Run `quick_validate.py` on all 3 skills
- Test skill invocation with sample problems
- Verify CLAUDE.md links resolve correctly

**Success Criteria**:

- 3 skills created in `./skills/` with YAML frontmatter + core instructions
- Each skill has progressive disclosure (references/ directory)
- CLAUDE.md updated with Hub-and-Spoke Link Farm
- All conventional commits (feat/docs prefixes)

## Alternatives Considered

### Alternative 1: Generic Skills (Not Domain-Specific)

**Approach**: Create generic investigation/query/documentation skills applicable to any domain

**Rejected Because**:

- Loses crypto/trading-specific optimizations (Parquet columnar format, range requests, cost sensitivity)
- User explicitly requested domain-specific skills
- Generic skills already exist in `~/.claude/skills/` (documentation-standards, etc.)
- Domain-specific skills provide more actionable guidance for crypto data workflows

### Alternative 2: Include ADR References as Examples

**Approach**: Reference ADR-0013/0014 as concrete examples in SKILL.md content

**Rejected Because**:

- User explicitly requested "no specific ADR-0013/0014 references"
- Skills become project-coupled (less portable to other crypto projects)
- ADRs may evolve independently (creates maintenance coupling)
- Generic/abstract skills age better (don't reference ephemeral implementations)

### Alternative 3: Create Single "Crypto Data Workflows" Skill

**Approach**: Combine all 3 patterns into one comprehensive skill

**Rejected Because**:

- Violates atomic skill principle (each skill solves ONE problem)
- Harder to discover (users must read entire skill to find relevant section)
- Monolithic SKILL.md anti-pattern (>5k words, poor progressive disclosure)
- Skills have different trigger conditions (investigation vs query vs documentation)

### Alternative 4: No Skills Extraction (Keep in Session Context)

**Approach**: Leave workflows embedded in ADR-0013/0014 documentation only

**Rejected Because**:

- Workflows get lost in project-specific context
- Not reusable for future crypto/trading data projects
- Violates knowledge capture principle (validated patterns should be preserved)
- User explicitly requested skill extraction

## References

- Investigation Reports: `/tmp/skill-design/` (3 sub-agent analyses)
- Existing Skills: `~/.claude/skills/` (22 skills, canonical structure)
- Related ADRs: [ADR-0013](0013-volume-rankings-timeseries.md), [ADR-0014](0014-easy-query-access.md)
- Skill Architecture Skill: `~/.claude/skills/skill-architecture/SKILL.md`
