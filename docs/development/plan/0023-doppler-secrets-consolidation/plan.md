# Doppler-Native Secrets Consolidation Implementation Plan

**adr-id**: 0023
**Date**: 2025-11-25
**Status**: In Progress
**Owner**: Data Pipeline Engineer
**Estimated Effort**: 70 minutes

## Context

This plan implements centralized secrets management using Doppler SecretOps (ADR-0023), consolidating all automation secrets from 1Password to Doppler.

**Current State**:

- 1Password service account (`pw7pefayhsn4yxq5yjpssljwb4`) manages 3 GitHub PATs in "GitHub Tokens" vault
- `~/.zshrc` has 1Password service account auto-load (lines 682-692)
- `~/.zshrc` permissions: 644 (world-readable) - SECURITY ISSUE
- Doppler `notifications/prd` has PUSHOVER_APP_TOKEN, PUSHOVER_USER_KEY
- GitHub repo has 5 secrets synced from Doppler

**Desired State**:

- All automation secrets in Doppler `notifications/prd`
- `~/.zshrc` uses Doppler service token instead of 1Password
- `~/.zshrc` permissions: 600 (owner-only)
- 1Password kept for personal passwords only
- GitHub Actions automatically sync from Doppler

**Architecture Decision**: ADR-0023

**Expected Outcomes**:

- Single source of truth for all automation secrets
- Simplified local automation (one tool: Doppler)
- Improved security (~/.zshrc permissions)
- Zero CI/CD changes needed

## Goals

### Primary Goals

- Fix `~/.zshrc` permissions (644 → 600)
- Migrate 3 GitHub tokens from 1Password to Doppler
- Update `~/.zshrc` to use Doppler service token
- Verify GitHub Actions sync working
- Clean up 1Password automation secrets
- Document architecture change

### Success Metrics

- `~/.zshrc` permissions are 600
- 3 GitHub tokens accessible via `doppler secrets get`
- GitHub repository shows 8 secrets (5 existing + 3 new)
- Local `doppler secrets get GH_TOKEN_TERRYLICA` works without browser auth
- 1Password "GitHub Tokens" vault has no automation secrets

### Non-Goals

- Migrate personal passwords from 1Password
- Set up Doppler environments (dev/staging) - deferred
- Automated secret rotation - deferred

## Plan

### Phase 1: Security Fix (5 minutes)

**Status**: Pending

**Tasks**:

1. Fix `~/.zshrc` permissions to 600

**Implementation**:

```bash
chmod 600 ~/.zshrc
```

**Validation**:

```bash
stat -f "%Lp %N" ~/.zshrc
# Expected: 600 /Users/terryli/.zshrc
```

### Phase 2: Migrate Secrets to Doppler (15 minutes)

**Status**: Pending

**Tasks**:

1. Retrieve GitHub tokens from 1Password (one last time)
2. Add tokens to Doppler `notifications/prd`
3. Verify secrets in Doppler

**Implementation**:

```bash
# Get tokens from 1Password
export OP_SERVICE_ACCOUNT_TOKEN=$(op item get pw7pefayhsn4yxq5yjpssljwb4 --fields credential --reveal)

GH_TOKEN_SEMANTIC=$(op item get "GitHub Terrylica Semantic-Release" --vault="GitHub Tokens" --fields token --reveal)
GH_TOKEN_EONLABS=$(op item get "GitHub Personal Access Token - EonLabs terrylica" --vault="GitHub Tokens" --fields token --reveal)
GH_TOKEN_TERRYLICA=$(op item get "GitHub Token terrylica GH_TOKEN_TERRYLICA" --vault="GitHub Tokens" --fields token --reveal)

# Add to Doppler
doppler secrets set \
  GH_TOKEN_SEMANTIC_RELEASE="$GH_TOKEN_SEMANTIC" \
  GH_TOKEN_EONLABS_PAT="$GH_TOKEN_EONLABS" \
  GH_TOKEN_TERRYLICA="$GH_TOKEN_TERRYLICA" \
  --project notifications --config prd
```

**Validation**:

```bash
doppler secrets --project notifications --config prd --only-names
# Expected: GH_TOKEN_SEMANTIC_RELEASE, GH_TOKEN_EONLABS_PAT, GH_TOKEN_TERRYLICA (+ existing)
```

### Phase 3: Update Local Environment (15 minutes)

**Status**: Pending

**Tasks**:

1. Create Doppler service token via dashboard
2. Update `~/.zshrc` to remove 1Password config, add Doppler token
3. Test local Doppler access

**Implementation**:

1. Create service token at: https://dashboard.doppler.com → `notifications` → `prd` → Access
2. Update `~/.zshrc`:

**Remove** (lines 682-692):

```bash
# 1Password Service Account for Automation
if command -v op >/dev/null 2>&1; then
    export OP_SERVICE_ACCOUNT_TOKEN=$(op item get pw7pefayhsn4yxq5yjpssljwb4 --fields credential --reveal 2>/dev/null || echo "")
    if [ -n "$OP_SERVICE_ACCOUNT_TOKEN" ]; then
        op vault list >/dev/null 2>&1 && export OP_SERVICE_ACCOUNT_ACTIVE=1
    fi
fi
```

**Add**:

```bash
# ========================================
# Doppler Service Token for Automation
# ========================================
# Zero-prompt automation using Doppler service token
# Project: notifications | Config: prd
if command -v doppler >/dev/null 2>&1; then
    export DOPPLER_TOKEN="dp.st.prd.xxxx"  # Replace with actual token
fi
```

**Validation**:

```bash
source ~/.zshrc
doppler secrets get GH_TOKEN_TERRYLICA --project notifications --config prd --plain
# Should return token without browser prompt
```

### Phase 4: Verify GitHub Actions Sync (10 minutes)

**Status**: Pending

**Tasks**:

1. Verify Doppler GitHub App syncs new secrets
2. Check GitHub repository secrets

**Validation**:

```bash
gh secret list --repo terrylica/binance-futures-availability
# Expected: 8 secrets (5 existing + 3 new GitHub tokens)
```

### Phase 5: Cleanup 1Password (10 minutes)

**Status**: Pending

**Tasks**:

1. Delete automation secrets from 1Password vault
2. Keep vault for potential personal use

**Implementation**:

```bash
export OP_SERVICE_ACCOUNT_TOKEN=$(op item get pw7pefayhsn4yxq5yjpssljwb4 --fields credential --reveal)

op item delete "GitHub Terrylica Semantic-Release" --vault="GitHub Tokens"
op item delete "GitHub Personal Access Token - EonLabs terrylica" --vault="GitHub Tokens"
op item delete "GitHub Token terrylica GH_TOKEN_TERRYLICA" --vault="GitHub Tokens"
```

**Note**: Keep service account and vault for personal password access if needed.

### Phase 6: Documentation (15 minutes)

**Status**: Pending

**Tasks**:

1. Update CLAUDE.md secrets section
2. Commit all changes with conventional commit

**Files to Modify**:

- `CLAUDE.md` - Remove 1Password references for automation
- `docs/architecture/decisions/0023-doppler-secrets-consolidation.md` - Mark complete

## Task List

This task list must stay synchronized with the plan above and the ADR.

### Security Tasks

- [ ] Fix ~/.zshrc permissions (chmod 600)

### Migration Tasks

- [ ] Retrieve 3 GitHub tokens from 1Password
- [ ] Add tokens to Doppler notifications/prd
- [ ] Verify tokens in Doppler dashboard/CLI

### Local Environment Tasks

- [ ] Create Doppler service token (MANUAL: dashboard)
- [ ] Update ~/.zshrc (remove 1Password, add Doppler)
- [ ] Test local Doppler access (no browser prompt)

### Verification Tasks

- [ ] Verify GitHub Actions Doppler sync (8 secrets)
- [ ] Test `doppler secrets get` for each token

### Cleanup Tasks

- [ ] Delete 3 automation items from 1Password vault
- [ ] Keep service account for personal use

### Documentation Tasks

- [ ] Update CLAUDE.md
- [ ] Commit with conventional commit message
- [ ] Push to GitHub

## Progress Log

Track execution here as work progresses:

### 2025-11-25 [Session Start] - Plan Created

- Created ADR-0023 (`docs/architecture/decisions/0023-doppler-secrets-consolidation.md`)
- Created implementation plan (this file)
- Audited current state:
  - 1Password vault: 4 items (3 PATs + 1 service account token)
  - ~/.zshrc: 644 permissions (security issue confirmed)
  - Doppler: 5 secrets in notifications/prd
  - GitHub: 5 secrets synced

### 2025-11-25 [Implementation] - All Phases Complete

**Phase 1: Security Fix**
- ✅ Fixed ~/.zshrc permissions: 644 → 600

**Phase 2: Migrate Secrets**
- ✅ Retrieved 3 GitHub tokens from 1Password
- ✅ Added to Doppler notifications/prd:
  - GH_TOKEN_SEMANTIC_RELEASE
  - GH_TOKEN_EONLABS_PAT
  - GH_TOKEN_TERRYLICA
- ✅ Verified: 8 secrets now in Doppler

**Phase 3: Update Local Environment**
- ✅ Created Doppler service token: "Claude Code Automation"
- ✅ Updated ~/.zshrc: removed 1Password config, added Doppler token
- ✅ Validated: `doppler secrets get` works without browser auth

**Phase 4: GitHub Actions Sync**
- ⚠️ New secrets need manual Doppler dashboard sync trigger
- Existing 5 secrets confirmed synced

**Phase 5: Cleanup 1Password**
- ✅ Deleted 3 automation items from "GitHub Tokens" vault
- ✅ Kept service account token for personal use

**Phase 6: Documentation**
- ✅ Updated CLAUDE.md with ADR-0022 and ADR-0023 entries
- ✅ Updated version to v1.3.0
- ✅ Updated plan progress log

## SLO Compliance

Per project SLOs, focus on 4 dimensions:

### Availability

- **Target**: Secrets accessible 99.99% (Doppler SLA)
- **Measurement**: Doppler dashboard uptime

### Correctness

- **Target**: Single source of truth, no sync issues
- **Measurement**: All secrets resolvable from Doppler

### Observability

- **Target**: Centralized audit trail
- **Measurement**: Doppler dashboard shows all access

### Maintainability

- **Target**: Single system to manage
- **Measurement**: No 1Password automation dependencies

## Error Handling Strategy

Per ADR-0003 (strict raise policy):

- **Doppler Failure**: Raise and fail, no fallback to 1Password
- **Token Retrieval Failure**: Raise immediately, log error
- **Sync Failure**: Check Doppler GitHub App configuration

## Rollback Plan

If migration fails:

1. 1Password items still exist (not deleted until Phase 5)
2. Re-enable 1Password service account in ~/.zshrc
3. Continue using two-tier architecture until resolved
