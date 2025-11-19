---
adr-id: 0017
title: Documentation Structure Migration Plan
status: approved
created: 2025-11-18
updated: 2025-11-18
owner: System Architect
---

# Documentation Structure Migration Plan

## Context

The binance-futures-availability project has 16 ADRs (Architecture Decision Records) and 10 implementation plans using an ad-hoc structure:

- ADRs: `docs/decisions/NNNN-*.md`
- Plans: `docs/plans/NNNN-*/plan.yaml` (OpenAPI-style YAML)

This structure functions but creates friction:

1. **Non-standard paths** prevent integration with ADR tooling (adr-tools, Log4brains)
2. **YAML plans** are less readable than narrative documentation
3. **No service catalog** blocks Backstage/TechDocs integration
4. **Implicit linkage** between ADRs and plans makes validation difficult

The project is production-ready (v1.0.0 released, GitHub Actions automation deployed) and needs documentation infrastructure that scales with maturity.

### Background

**Current State**:

- 16 ADRs documenting schema design, storage technology, automation, volume metrics
- 10 YAML implementation plans (v1.0.0, 0007-0015)
- Cross-references in CLAUDE.md (project memory) and README.md
- No machine-readable service metadata

**Problem**:

- New contributors unfamiliar with project struggle to find ADRs (non-standard path)
- YAML plans difficult to review in pull requests (structural diffs, not narrative)
- Cannot auto-validate that plans reference valid ADRs
- Missing from Backstage service catalog (catalog-info.yaml)

## Goals

1. **Standardize paths** to enable ADR tooling integration
   - ADRs: `docs/architecture/decisions/NNNN-slug.md` (MADR standard)
   - Plans: `docs/development/plan/NNNN-slug/plan.md` (Google Design Doc)

2. **Establish ADR↔plan↔code traceability**
   - Plans include `adr-id=NNNN` frontmatter
   - Enable validation: "Does plan reference valid ADR?"

3. **Improve readability**
   - Convert YAML plans to narrative Google Design Doc markdown
   - Format: Context → Goals → Design → Alternatives

4. **Enable tool integration**
   - Create `catalog-info.yaml` for Backstage
   - Compatible with adr-tools, Log4brains, TechDocs

5. **Preserve git history**
   - Use `git mv` to maintain file provenance
   - No content loss during migration

## Non-Goals

1. **NOT changing ADR content** - This is a structural migration, not content review
2. **NOT changing decision outcomes** - ADR statuses (Accepted/Superseded) remain unchanged
3. **NOT adding new ADRs** - Migration only, no new architecture decisions
4. **NOT optimizing performance/security** - SLO scope: maintainability, observability, correctness only
5. **NOT backward compatibility** - External links to old paths will break (acceptable tradeoff)

## Design

### High-Level Approach

```
Phase 1: Structure     Phase 2: Migration      Phase 3: Validation
┌─────────────────┐   ┌──────────────────┐   ┌─────────────────┐
│ Create new dirs │ → │ Move ADRs + plans│ → │ Validate refs   │
│ - architecture/ │   │ - git mv ADRs    │   │ - Run tests     │
│ - development/  │   │ - Convert YAMLs  │   │ - Check linkage │
└─────────────────┘   └──────────────────┘   └─────────────────┘
```

### Directory Structure (New)

```
binance-futures-availability/
├── docs/
│   ├── architecture/
│   │   └── decisions/                    # MADR-compliant ADRs
│   │       ├── 0001-schema-design-daily-table.md
│   │       ├── 0002-storage-technology-duckdb.md
│   │       └── ... (0003-0017)
│   ├── development/
│   │   └── plan/                         # Google Design Doc plans
│   │       ├── 0001-schema-design/plan.md
│   │       ├── 0002-storage-technology/plan.md
│   │       └── ... (0003-0017)
│   ├── guides/                           # User guides (unchanged)
│   ├── operations/                       # Operations docs (unchanged)
│   ├── schema/                           # JSON schemas (unchanged)
│   └── [legacy paths deprecated]
│       ├── decisions/ → DEPRECATED
│       └── plans/ → DEPRECATED
├── catalog-info.yaml                     # Backstage service catalog
└── ...
```

### Migration Steps

#### Step 1: Create Directory Structure

```bash
mkdir -p docs/architecture/decisions/
mkdir -p docs/development/plan/
```

**Validation**: Directories exist with correct permissions

#### Step 2: Move ADRs (Preserve Git History)

```bash
# Move ADRs 0001-0016
for adr in docs/decisions/000*.md; do
  basename=$(basename "$adr")
  git mv "$adr" "docs/architecture/decisions/$basename"
done
```

**Validation**:

- All 16 ADRs present in new location
- `git log --follow` shows history preserved
- No files left in `docs/decisions/`

#### Step 3: Convert YAML Plans to Google Design Doc

For each `docs/plans/NNNN-*/plan.yaml`:

**Input (YAML)**:

```yaml
plan_id: v1.0.0
version: 1.0.0
title: Initial Implementation
phases:
  - name: Phase 1
    deliverables: [...]
```

**Output (Markdown)**:

```markdown
---
adr-id: 0001
title: Schema Design Plan
status: implemented
---

# Schema Design Plan

## Context

[Narrative explanation...]

## Goals

- Goal 1
- Goal 2

## Design

[Design narrative...]
```

**Conversion Logic**:

1. Extract metadata (plan_id, version) → frontmatter (adr-id, title)
2. Transform phases[] → "Design" section with narrative
3. Transform deliverables[] → "Goals" section
4. Add "Context" (from ADR context)
5. Add "Alternatives" (from ADR alternatives)

**Tool**: Manual conversion (10 plans, ~30 min each = 5 hours)
**Alternative**: Script conversion (risk: loss of narrative nuance)
**Decision**: Manual conversion to ensure readability

#### Step 4: Create catalog-info.yaml

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: binance-futures-availability
  description: Daily availability tracking for Binance USDT perpetual futures
  tags:
    - duckdb
    - data-engineering
    - binance
  annotations:
    github.com/project-slug: terryli/binance-futures-availability
spec:
  type: service
  lifecycle: production
  owner: data-team
  system: crypto-data-platform
```

**Validation**: Validates against Backstage schema

#### Step 5: Update Cross-References

Update paths in:

- `CLAUDE.md`: Lines 19-83 (ADR summaries)
- `README.md`: Lines 260-271 (ADR links)
- Any code comments referencing ADR paths

**Tool**: Find & replace

```bash
# CLAUDE.md
sed -i '' 's|docs/decisions/|docs/architecture/decisions/|g' CLAUDE.md

# README.md
sed -i '' 's|docs/decisions/|docs/architecture/decisions/|g' README.md

# Code comments (if any)
find src/ -type f -name "*.py" -exec sed -i '' 's|docs/decisions/|docs/architecture/decisions/|g' {} \;
```

**Validation**:

- `grep -r "docs/decisions/" .` returns 0 matches (except deprecated directory)
- All ADR links resolve correctly

#### Step 6: Deprecate Old Directories

```bash
# Create deprecation notices
echo "# DEPRECATED: Moved to docs/architecture/decisions/" > docs/decisions/README.md
echo "# DEPRECATED: Moved to docs/development/plan/" > docs/plans/README.md
```

**Do NOT delete** old directories (git history, external links may reference)

### Plan→ADR Linkage Mechanism

**Frontmatter in plan.md**:

```yaml
---
adr-id: 0017 # Links to ADR-0017
title: Documentation Structure Migration Plan
status: approved
---
```

**Validation Script**:

```bash
#!/bin/bash
# validate-adr-plan-linkage.sh
for plan in docs/development/plan/*/plan.md; do
  adr_id=$(grep "^adr-id:" "$plan" | cut -d' ' -f2)
  adr_file="docs/architecture/decisions/$(printf '%04d' $adr_id)-*.md"

  if [ ! -f $adr_file ]; then
    echo "ERROR: Plan $plan references non-existent ADR-$adr_id"
    exit 1
  fi
done
echo "✅ All plans reference valid ADRs"
```

**CI Integration**: Add to GitHub Actions workflow

### Rollback Plan

If migration fails validation:

1. **Revert ADR moves**: `git revert <commit>`
2. **Delete converted plans**: `rm -rf docs/development/plan/`
3. **Restore YAML plans**: `git checkout docs/plans/`
4. **Revert reference updates**: `git checkout CLAUDE.md README.md`

Git history preserved, so rollback is atomic.

## Alternatives Considered

### Alternative 1: Keep YAML Plans

Convert ADR paths but keep plans as `plan.yaml`.

**Rejected because**:

- YAML diffs difficult to review in PRs (structural changes obscure intent)
- Google Design Doc format industry-standard, more familiar to engineers
- Narrative markdown forces "why" over "how" (intent over implementation)

### Alternative 2: Gradual Migration

Migrate ADRs first, plans later.

**Rejected because**:

- Two documentation formats create confusion
- ADR↔plan linkage broken during interim period
- Validation scripts need to handle mixed state

### Alternative 3: Regenerate Plans from Scratch

Delete old plans, write new Google Design Docs from ADR content.

**Rejected because**:

- Loss of implementation history (phases, milestones, actual decisions made)
- High effort (rewrite 10 plans from scratch)
- Violates "copy/move existing files to save tokens" principle

## Cross-Cutting Concerns

### SLO Alignment

| SLO                 | Impact                                       | Mitigation                              |
| ------------------- | -------------------------------------------- | --------------------------------------- |
| **Maintainability** | ✅ Improved (standard paths)                 | Validation scripts ensure correctness   |
| **Observability**   | ✅ Improved (explicit ADR↔plan linkage)     | CI validates linkage on every commit    |
| **Correctness**     | ⚠️ Risk (broken references during migration) | Batch update + validation before commit |
| **Availability**    | ➖ No impact (docs-only change)              | N/A                                     |

### Error Handling

All migration steps follow **raise+propagate** policy:

- `git mv` failure → abort immediately, no fallback
- Validation failure → abort, no silent continue
- Broken reference found → fail CI, no default placeholder

No retries, no silent handling, no default values.

### Documentation Standards

- ✅ **No promotional language**: Focus on technical rationale
- ✅ **Abstractions over implementation**: Explain "standard paths enable tooling" not "how mkdir works"
- ✅ **Intent over implementation**: Document _why_ Google Design Doc format, not just _how_ to convert YAML

### Backward Compatibility

**Explicitly NOT supported**:

- Old ADR paths (`docs/decisions/`) will have deprecation notice
- External links to old paths will break (acceptable tradeoff)
- No symlinks or redirects (clean break)

Rationale: Simplicity over compatibility. Project is early enough that external references minimal.

### Validation & Testing

**Pre-commit validation**:

1. All ADRs accessible at new paths
2. All plans contain `adr-id=NNNN`
3. All `adr-id` references point to existing ADRs
4. No broken cross-references in CLAUDE.md, README.md
5. Full test suite passes

**Post-migration monitoring**:

- Watch for 404s in documentation links (GitHub Issues, external references)
- Monitor contributor confusion (PR review feedback)

## Timeline & Milestones

### Milestone 1: Structure & ADRs (30 minutes)

- [ ] Create `docs/architecture/decisions/`
- [ ] Create `docs/development/plan/`
- [ ] Move ADR-0001 through ADR-0016 (`git mv`)
- [ ] Validate git history preserved

### Milestone 2: Plans Conversion (5 hours)

- [ ] Convert plan v1.0.0 (YAML → markdown)
- [ ] Convert plans 0007-0015 (9 plans × 30 min)
- [ ] Add `adr-id` frontmatter to all plans
- [ ] Validate plan→ADR linkage

### Milestone 3: Integration (1 hour)

- [ ] Create `catalog-info.yaml`
- [ ] Update CLAUDE.md cross-references
- [ ] Update README.md cross-references
- [ ] Add deprecation notices to old dirs

### Milestone 4: Validation (30 minutes)

- [ ] Run ADR↔plan linkage validation script
- [ ] Run full test suite (`pytest tests/`)
- [ ] Check for broken links in docs
- [ ] Review git diff for unexpected changes

**Total Effort**: ~7 hours
**Dependencies**: None (standalone migration)

## Success Metrics

1. **Structural correctness**:
   - ✅ All 16 ADRs in `docs/architecture/decisions/`
   - ✅ All 10+ plans in `docs/development/plan/`
   - ✅ Zero files in old `docs/decisions/` (except deprecation notice)

2. **Linkage validation**:
   - ✅ All plans contain `adr-id=NNNN`
   - ✅ All `adr-id` references resolve to existing ADRs
   - ✅ Zero broken cross-references

3. **Git history preservation**:
   - ✅ `git log --follow` shows full history for each ADR
   - ✅ Authorship preserved

4. **Tool compatibility**:
   - ✅ `catalog-info.yaml` validates against Backstage schema
   - ✅ ADR paths recognized by adr-tools (if installed)

5. **Test suite**:
   - ✅ All tests pass (pytest: 16 passed, 1 skipped)
   - ✅ No broken imports or path references in code

## Open Questions

1. **Should we create redirects for old ADR paths?**
   - Decision: No. Clean break preferred over maintenance burden of redirects.

2. **Should plan conversion be automated?**
   - Decision: Manual conversion for first 10 plans to ensure quality. Automate for future plans once pattern validated.

3. **Should we add ADR status badges?**
   - Decision: Defer to future ADR. Focus migration first, enhancements later.

## Related Work

- ADR-0008: Workspace Organization (predecessor cleanup decision)
- ADR-0017: Documentation Structure Migration (this decision)
- [MADR specification](https://adr.github.io/madr/)
- [Google Design Docs guide](https://www.industrialempathy.com/posts/design-docs-at-google/)
