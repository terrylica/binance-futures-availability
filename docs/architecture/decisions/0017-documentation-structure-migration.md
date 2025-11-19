# ADR-0017: Documentation Structure Migration

**Status**: Accepted

**Date**: 2025-11-18

**Deciders**: System Architect

**Technical Story**: Migrate from ad-hoc documentation structure to standardized doc-as-code architecture that maintains ADR ↔ plan ↔ todo list ↔ code synchronization.

## Context and Problem Statement

The project currently uses a functional but non-standard documentation structure:

- ADRs in `docs/decisions/NNNN-*.md` (16 ADRs: 0001-0016)
- Plans in `docs/plans/NNNN-*/plan.yaml` (OpenAPI-style YAML)
- No service catalog metadata for tool integration (Backstage, etc.)

This structure works but lacks:

1. **Standardization**: Non-standard paths prevent tooling integration (Backstage, ADR viewers)
2. **Traceability**: No explicit `adr-id` linkage between ADRs and plans
3. **Format consistency**: YAML plans are less readable than narrative markdown
4. **Discoverability**: Non-standard paths harder for new contributors to find

As the project matures toward production use (v1.0.0 released, GitHub Actions automation deployed), we need documentation infrastructure that supports:

- Automated ADR→plan→code validation
- Service catalog integration (Backstage)
- Machine-readable metadata
- Industry-standard tooling compatibility

## Decision Drivers

- **Maintainability SLO**: Documentation must be discoverable and maintainable by new contributors
- **Observability SLO**: Clear traceability from architecture decisions to implementation
- **Correctness SLO**: Doc-as-code validation prevents drift between documentation and code
- **Industry standards**: Align with MADR (Markdown Architecture Decision Records) and Google Design Doc formats

## Considered Options

### Option 1: Keep Current Structure (Status Quo)

**Structure**:

```
docs/
├── decisions/NNNN-slug.md (ADRs)
├── plans/NNNN-slug/plan.yaml (OpenAPI-style YAML)
└── [other docs]
```

**Pros**:

- No migration effort required
- Existing 16 ADRs already functional
- Team familiar with current structure

**Cons**:

- Non-standard paths block tooling integration
- YAML plans less readable than narrative docs
- No service catalog metadata
- Difficult to validate ADR↔plan synchronization

### Option 2: Migrate to Standardized Structure (CHOSEN)

**Structure**:

```
docs/
├── architecture/
│   └── decisions/NNNN-slug.md (MADR format)
├── development/
│   └── plan/NNNN-slug/plan.md (Google Design Doc)
└── [other docs]
catalog-info.yaml (Backstage service catalog)
```

**Pros**:

- **Standard paths**: `docs/architecture/decisions/` recognized by ADR tools (adr-tools, Log4brains)
- **Narrative plans**: Google Design Doc format more readable than YAML
- **Explicit linkage**: Plans include `adr-id=NNNN` for traceability
- **Tool integration**: catalog-info.yaml enables Backstage, TechDocs
- **Validation**: Can auto-validate ADR↔plan synchronization
- **Industry alignment**: Follows MADR specification, Google SRE practices

**Cons**:

- Migration effort: Move 16 ADRs + 10 plans
- Update cross-references in CLAUDE.md, README.md, code comments
- Short-term documentation drift risk during migration

### Option 3: Hybrid Approach

Keep old ADRs in place, new ADRs use new structure.

**Pros**:

- Minimal migration effort
- No risk of breaking existing references

**Cons**:

- Two documentation systems create confusion
- Partial tooling compatibility
- Eventual migration still needed

## Decision Outcome

**Chosen option**: **Option 2: Migrate to Standardized Structure**

### Rationale

1. **Maintainability**: Industry-standard paths make project more accessible to new contributors familiar with MADR/Google Design Doc patterns

2. **Observability**: Explicit `adr-id` linkage in plans enables automated validation:

   ```bash
   # Can validate plan references valid ADR
   grep "adr-id=0017" docs/development/plan/0017-*/plan.md
   ```

3. **Correctness**: Narrative Google Design Doc format forces authors to explain **intent** ("why") over **implementation** ("how"), reducing documentation drift

4. **Tool Ecosystem**: Enables integration with:
   - Backstage (service catalog via catalog-info.yaml)
   - Log4brains (ADR visualization)
   - TechDocs (automated doc site generation)
   - adr-tools (ADR management CLI)

5. **One-time cost**: Migration effort (estimated 2-3 hours) is justified by long-term maintainability gains

### Implementation Strategy

**Phase 1: Create New Structure**

```bash
mkdir -p docs/architecture/decisions/
mkdir -p docs/development/plan/
```

**Phase 2: Move ADRs** (preserve git history)

```bash
for adr in docs/decisions/*.md; do
  git mv "$adr" "docs/architecture/decisions/$(basename $adr)"
done
```

**Phase 3: Convert Plans** (YAML → Google Design Doc markdown)

- Transform `plan.yaml` to `plan.md` with sections: Context, Goals, Non-Goals, Design, Alternatives
- Add `adr-id=NNNN` frontmatter linkage

**Phase 4: Update References**

- CLAUDE.md: Update ADR paths
- README.md: Update ADR links
- Source code comments: Update ADR reference paths

**Phase 5: Create Service Catalog**

- Create `catalog-info.yaml` with component metadata
- Link to documentation paths

### Validation Criteria

✅ All ADRs accessible at `docs/architecture/decisions/NNNN-*.md`
✅ All plans accessible at `docs/development/plan/NNNN-*/plan.md`
✅ All plans contain `adr-id=NNNN` linkage
✅ No broken cross-references in CLAUDE.md, README.md
✅ catalog-info.yaml validates against Backstage schema
✅ Full test suite passes (pytest)

## Consequences

### Positive

- **Tooling compatibility**: Can use adr-tools, Log4brains, Backstage out-of-box
- **Discoverability**: Standard paths make documentation easier to find
- **Traceability**: Explicit ADR↔plan linkage enables validation
- **Readability**: Google Design Doc narrative format more approachable than YAML
- **Automation potential**: Can build ADR→plan→code validation into CI/CD
- **Industry alignment**: Easier onboarding for engineers familiar with MADR/Google SRE practices

### Negative

- **Migration effort**: 2-3 hours to move 16 ADRs + 10 plans
- **Learning curve**: Team must learn Google Design Doc format (mitigated by template)
- **Temporary drift**: Cross-references may break during migration (mitigated by batch update)
- **Path changes**: External links to ADRs will break (mitigated by GitHub redirects)

### Neutral

- **File count unchanged**: Same number of files, just reorganized
- **Content largely unchanged**: ADRs remain MADR format, plans just converted YAML→markdown
- **Git history preserved**: Using `git mv` maintains file history

## Compliance

### SLOs Addressed

- ✅ **Maintainability**: Standardized structure reduces onboarding time for new contributors
- ✅ **Observability**: Explicit ADR↔plan linkage makes decision traceability transparent
- ✅ **Correctness**: Narrative format forces "why" over "how", reducing documentation drift
- ✅ **Availability**: N/A (documentation change doesn't affect service availability)

### Error Handling

Migration script will:

- ✅ Raise errors immediately if `git mv` fails (no silent fallbacks)
- ✅ Validate all cross-references updated before commit
- ✅ Run full test suite to detect broken imports
- ✅ Abort if any validation fails (fail-fast)

### Documentation Standards

- ✅ **No promotional language**: Focus on technical rationale
- ✅ **Abstractions over implementation**: Explain "why standard paths" not "how to mkdir"
- ✅ **Intent over implementation**: Document decision drivers, not just commands

## Links

- [MADR specification](https://adr.github.io/madr/)
- [Google Design Docs](https://www.industrialempathy.com/posts/design-docs-at-google/)
- [Backstage catalog format](https://backstage.io/docs/features/software-catalog/descriptor-format)
- ADR-0008: Workspace Organization (predecessor decision on documentation cleanup)

## Notes

This ADR itself follows the new format and serves as example for future ADRs. The associated plan is at `docs/development/plan/0017-documentation-structure-migration/plan.md`.
