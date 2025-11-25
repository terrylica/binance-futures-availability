# ADR-0023: Doppler-Native Secrets Consolidation

**Status**: Accepted

**Date**: 2025-11-25

**Deciders**: Data Pipeline Engineer

**Technical Story**: Consolidate all automation secrets to Doppler SecretOps, remove 1Password from automation workflows, establish single source of truth for secrets management.

## Context and Problem Statement

Current secrets architecture uses two systems:

- **1Password Service Account**: Local automation (Claude Code) with GitHub tokens in "GitHub Tokens" vault
- **Doppler SecretOps**: CI/CD automation with Pushover secrets synced via GitHub App

This creates:

1. **Complexity**: Two systems to maintain, rotate, and audit
2. **Inconsistency**: Local vs CI/CD use different secret sources
3. **Security Risk**: `~/.zshrc` with 644 permissions (world-readable)
4. **Mental Overhead**: Remembering which system has which secrets

User requirement: Consolidate to single secrets platform (Doppler chosen).

## Decision Drivers

- **Maintainability SLO**: Single source of truth reduces cognitive load
- **Observability SLO**: Centralized audit trail in Doppler dashboard
- **Availability SLO**: Doppler GitHub App auto-syncs to repository secrets (already working)
- **Correctness SLO**: Consistent secret access pattern across local and CI/CD

## Considered Options

### Option 1: 1Password Everywhere

Use 1Password service account for both local and CI/CD:

**Pros**:

- Single system
- Biometric integration (when not using service account)
- Existing subscription

**Cons**:

- No native GitHub App integration
- Requires secret injection in workflows
- Service account token management overhead
- No environment separation (dev/staging/prod)

### Option 2: Doppler Everywhere (CHOSEN)

Consolidate all automation secrets to Doppler:

**Pros**:

- GitHub App already configured and syncing (ADR-0022)
- Native environment management (dev/staging/prod configs)
- Git-style versioning and rollback
- Zero CI/CD changes needed (already using Doppler)
- Service tokens for local automation

**Cons**:

- Requires Doppler service token for local access
- Less biometric integration than 1Password

### Option 3: Hybrid (Status Quo)

Keep both systems:

**Pros**:

- No migration effort

**Cons**:

- Dual maintenance burden
- Inconsistent access patterns
- Higher complexity

## Decision Outcome

**Chosen Option**: Option 2 (Doppler Everywhere)

**Rationale**:

1. Doppler GitHub App already working (ADR-0022 implementation)
2. Native environment separation (dev/staging/prod)
3. Zero CI/CD changes needed
4. Centralized audit trail
5. 1Password kept for personal passwords only

## Implementation Details

### Secrets Architecture After Migration

```
Doppler (notifications/prd)
├── PUSHOVER_APP_TOKEN     # Existing
├── PUSHOVER_USER_KEY      # Existing
├── GH_TOKEN_SEMANTIC_RELEASE  # Migrated from 1Password
├── GH_TOKEN_EONLABS_PAT   # Migrated from 1Password
└── GH_TOKEN_TERRYLICA     # Migrated from 1Password

    ↓ Doppler GitHub App Auto-Sync ↓

GitHub Repository Secrets
├── PUSHOVER_APP_TOKEN
├── PUSHOVER_USER_KEY
├── GH_TOKEN_SEMANTIC_RELEASE
├── GH_TOKEN_EONLABS_PAT
└── GH_TOKEN_TERRYLICA

1Password (Personal Only)
└── No automation secrets (just personal passwords)
```

### Local Access Pattern

```bash
# Via Doppler service token
export DOPPLER_TOKEN="dp.st.prd.xxxx"
doppler secrets get GH_TOKEN_TERRYLICA --project notifications --config prd --plain
```

### Security Fix

```bash
# ~/.zshrc must be owner-only
chmod 600 ~/.zshrc
```

## Consequences

### Positive

- Single source of truth for all automation secrets
- Doppler GitHub App handles CI/CD sync automatically
- Git-style versioning and rollback for secrets
- Centralized audit trail in Doppler dashboard
- Environment separation (future: dev/staging/prod)

### Negative

- Requires Doppler service token setup for local automation
- Less biometric integration than 1Password for local use
- Requires manual Doppler dashboard access for secret rotation

### Risks

- **Doppler Outage**: 99.99% SLA (better than GitHub Actions 99.9%)
- **Token Compromise**: Rotate via Doppler dashboard, revoke immediately
- **Migration Failure**: 1Password items kept until verified in Doppler

## Compliance

### SLOs

- **Availability**: Doppler 99.99% SLA
- **Correctness**: Single source eliminates sync issues
- **Observability**: Centralized audit trail
- **Maintainability**: Single system to manage

### Error Handling (ADR-0003)

- Doppler failures raise immediately (strict policy)
- No silent fallback to 1Password
- Clear error messages for missing secrets

## References

- **Related ADRs**: ADR-0022 (Pushover Notifications - established Doppler pattern)
- **Implementation Plan**: `docs/development/plan/0023-doppler-secrets-consolidation/plan.md`
- **Doppler Dashboard**: https://dashboard.doppler.com
- **1Password Vault**: "GitHub Tokens" (to be cleaned up)
