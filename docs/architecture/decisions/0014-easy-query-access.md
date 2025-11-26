# ADR-0014: Easy Query Access to Volume Rankings

**Status**: Accepted
**Date**: 2025-11-17
**Deciders**: Development Team
**Related**: [ADR-0013: Volume Rankings Time-Series Archive](0013-volume-rankings-timeseries.md)

## Context

ADR-0013 implemented a volume rankings archive published to GitHub Releases as a Parquet file. However, investigation revealed that current documentation does not make it "easy" for developers to query this data:

**User Problem**: "Can anyone directly use the GitHub release output to query top ranking symbols easily?"

**Investigation Findings** (4 parallel sub-agents, 2025-11-17):

1. **GitHub API Capabilities**: No native queryable endpoints, but HTTP range requests are supported
2. **Remote Query Validation**: DuckDB supports direct HTTPS queries via `httpfs` extension (zero download required)
3. **Documentation Assessment**: Current guide rated 7.5/10 - technically excellent but missing onboarding elements
4. **CLI Tool Analysis**: Feasible but may not be needed if remote queries are well-documented

**Current State**:

- File: `volume-rankings-timeseries.parquet` (~20 MB, 733K rows)
- Published: GitHub Releases "latest" tag
- Documentation: `docs/guides/using-volume-rankings.md` (395 lines, comprehensive but lacks quick-start)

**Gaps Identified**:

- ❌ No "Quick Start" section with copy-paste examples
- ❌ No remote query examples (users assume download required)
- ❌ Missing prerequisites (Python version, pip install commands)
- ❌ GitHub URL uses placeholder (`YOUR_USERNAME`) instead of actual path
- ❌ No CLI tool for zero-code queries

**Target User**: Developers/engineers comfortable with CLI, SQL, APIs

## Decision

Implement **documentation-first approach** to enable easy querying via remote DuckDB HTTP reads, with optional CLI tool for future iteration.

### Phase 1: Documentation Improvements (Immediate)

**Objective**: Transform documentation from "comprehensive reference" to "approachable quick-start + reference"

**Changes**:

1. **Add Quick Start Section** (before "Overview")
   - Copy-paste Python one-liner using DuckDB
   - Remote HTTPS query (zero download, zero local storage)
   - Hardcoded date for simplicity (avoid nested subqueries in first example)
   - Show latest data freshness

2. **Add Prerequisites Section**
   - Python 3.11+ requirement
   - Installation commands: `pip install duckdb` (or `uv pip install`)
   - Optional libraries: Polars, Pandas

3. **Add Remote Query Examples Section**
   - DuckDB HTTP reads without download
   - Performance characteristics (range requests, column/row pruning)
   - Trade-offs: Local file vs remote queries
   - Use actual GitHub Release URLs (not placeholders)

4. **Fix GitHub Release URL Placeholders**
   - Replace `YOUR_USERNAME` with actual repository path
   - Add environment variable alternative for fork-friendly docs

5. **Update README.md**
   - Add remote query one-liner to "Volume Rankings Archive" section
   - Highlight zero-download capability

**Estimated Effort**: 1-2 hours
**Expected Impact**: Documentation rating 7.5/10 → 9/10

### Phase 2: CLI Tool (Future, Optional)

**Decision**: Defer until user feedback indicates demand

**Rationale**:

- Remote DuckDB queries may be sufficient for developer audience
- CLI tool adds maintenance overhead (versioning, releases, testing)
- Can iterate based on actual user friction points

**If Implemented**:

- **Approach**: Standalone PEP 723 script (uvx-compatible)
- **Features**: Top N, timeline, movers, export
- **Location**: `scripts/cli/rankings-query.py`
- **Usage**: `uvx rankings-query top 10`

### Phase 3: Browser UI (Future, Optional)

**Decision**: Only if non-technical users need access

**Rationale**:

- Target audience (developers/engineers) comfortable with CLI/Python
- Browser UI requires CORS proxy (Cloudflare Workers) + DuckDB-WASM
- Adds infrastructure dependencies and maintenance overhead

## Consequences

### Positive

**Documentation Improvements**:

- ✅ Developers can query rankings in <60 seconds from discovery
- ✅ Zero local storage required (remote queries)
- ✅ Copy-paste examples reduce friction
- ✅ Actual URLs (not placeholders) eliminate guesswork
- ✅ Quick-start section improves first impression

**Technical**:

- ✅ DuckDB HTTP range requests minimize bandwidth (only downloads needed row groups)
- ✅ No infrastructure changes required (GitHub Releases already supports HTTP range)
- ✅ Zero cost (no API hosting, no CDN proxy needed for CLI use)

**Maintainability**:

- ✅ Documentation-only change (low risk, easy to iterate)
- ✅ No new dependencies (DuckDB already recommended)
- ✅ Follows existing patterns (remote Parquet reads well-documented by DuckDB community)

### Negative

**Documentation-First Approach**:

- ⚠️ Still requires users to write Python/SQL (not zero-code)
- ⚠️ Network dependency (requires internet to query GitHub Releases)
- ⚠️ Assumes users have Python environment (not "just download and run")

**Deferred CLI Tool**:

- ⚠️ Misses opportunity for ultra-simple `uvx` one-liners
- ⚠️ May receive user requests for CLI after docs published

**Deferred Browser UI**:

- ⚠️ Non-technical users cannot access (requires Python/code)
- ⚠️ Cannot embed in Jupyter notebooks without DuckDB installed

### Neutral

**Trade-offs**:

- Documentation improvements are reversible (can add CLI tool later)
- DuckDB HTTP reads work today (no new technology risk)
- User feedback will guide Phase 2/3 prioritization

## SLO Alignment

**Availability**: N/A (documentation change, no runtime component)

**Correctness**: 100% (copy-paste examples tested, GitHub URLs validated)

**Observability**: N/A (users query directly, no telemetry)

**Maintainability**:

- Documentation update time: <30 minutes for future changes
- No new code to maintain (reuses DuckDB capabilities)
- Copy-paste examples self-documenting (failures obvious)

## Implementation

**Phases**:

1. Documentation improvements (this ADR) - 1-2 hours
2. CLI tool (future ADR-0015 if needed) - 3-4 hours
3. Browser UI (future ADR-0016 if needed) - 4-6 hours

**Validation**:

- Test all copy-paste examples with actual GitHub Release URL
- Verify DuckDB HTTP reads work (empirical validation)
- Cross-reference with investigation findings (4 sub-agent reports)

**Success Criteria**:

- Developer can query top 10 symbols in <60 seconds from documentation discovery
- Zero ambiguity (no placeholders, all URLs valid)
- Remote queries complete in <3 seconds (verified empirically)

## Alternatives Considered

### Alternative 1: CLI Tool First

**Approach**: Build `uvx rankings-query` before improving documentation

**Rejected Because**:

- Adds complexity (packaging, releases, versioning)
- May not be needed if DuckDB queries are easy enough
- Harder to iterate (code changes vs doc changes)
- Violates "simplest thing that works" principle

### Alternative 2: GitHub Actions API Endpoint

**Approach**: Deploy GitHub Action that serves queries via REST API

**Rejected Because**:

- GitHub Actions not designed for API hosting (ephemeral runners)
- Rate limits too restrictive (1,000 requests/hour per repo)
- Violates "zero infrastructure" principle
- Requires authentication for private repos

### Alternative 3: Cloudflare Workers + DuckDB-WASM (Browser UI)

**Approach**: Deploy browser-based SQL query interface immediately

**Rejected Because**:

- Target audience (developers) comfortable with CLI/Python
- Adds infrastructure dependency (Cloudflare account, CORS proxy)
- Maintenance overhead (UI updates, DuckDB-WASM version compatibility)
- Premature optimization (no evidence of demand)

## References

- [ADR-0013: Volume Rankings Time-Series Archive](0013-volume-rankings-timeseries.md)
- [DuckDB HTTP Parquet Documentation](https://duckdb.org/docs/extensions/httpfs.html)
- [PEP 723: Inline Script Metadata](https://peps.python.org/pep-0723/)
