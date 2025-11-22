# Pushover Workflow Notifications Implementation Plan

**adr-id**: 0022
**Date**: 2025-11-22
**Status**: In Progress
**Owner**: DevOps Engineer
**Estimated Effort**: 2 hours
**Actual Effort**: TBD

## Context

This plan implements real-time Pushover notifications for GitHub Actions workflow runs (ADR-0022), eliminating manual workflow monitoring overhead.

**Current State**:

- GitHub Actions runs daily at 3AM UTC (scheduled cron)
- User must manually check GitHub UI for workflow status
- Local monitoring script (`scripts/operations/monitor_workflow.sh`) provides Pushover notifications but requires manual execution
- No instant feedback on workflow failures/successes

**Desired State**:

- Pushover notifications arrive automatically on all workflow runs (success/failure/cancelled)
- Rich context included: database stats, validation status, volume rankings status, run details
- Consistent UX between local and CI workflows
- Centralized secret management via Doppler

**User Requirement**:

> "When the CI/CD running on GitHub after successful running or even after whatever status where I get pushed over a notification at the end."

**Architecture Decision**: ADR-0022

**Research Base**: Planning agent research on Pushover + GitHub Actions integration patterns

**Expected Outcomes**:

- Instant workflow status visibility (no manual GitHub UI checks)
- 30 hours/year time savings (5 min/day × 365 days)
- Faster incident response (immediate failure detection)
- ROI: 1,500% (2 hours invested, 30 hours/year saved)

## Goals

### Primary Goals

- ✅ Add Doppler SecretOps integration to workflow (fetch PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY)
- ✅ Implement Pushover notification step with conditional formatting (success/failure/cancelled)
- ✅ Include comprehensive database statistics in notifications
- ✅ Ensure notifications run on all workflow statuses (`if: always()`)
- ✅ Validate workflow syntax and test notifications

### Success Metrics

- Pushover notification arrives within 5 seconds of workflow completion
- Notification includes: latest_date, total_records, available_count, validation_status, rankings_status
- All three statuses trigger notifications (success, failure, cancelled)
- Secrets managed via Doppler (no manual GitHub secret updates needed)
- Workflow still passes even if notification fails (non-blocking)
- Zero functional regressions (all tests pass)

### Non-Goals

- Email notifications (user prefers Pushover)
- Slack/Discord integration → Deferred to future
- Pre-built GitHub Action usage (user chose custom curl approach)
- Notification batching/aggregation (one notification per workflow run)

## Plan

### Phase 1: Secret Setup (15 minutes)

**Status**: Pending

**Tasks**:

1. Verify Doppler "notifications" project configuration
2. Add GitHub repository secret: `DOPPLER_TOKEN`
3. Confirm Doppler secrets exist: `PUSHOVER_API_TOKEN`, `PUSHOVER_USER_KEY`

**Manual Steps**:

```bash
# 1. Get Doppler service token
#    Navigate: https://dashboard.doppler.com/workplace/*/projects/notifications/configs/prd/access
#    Create service token with read access

# 2. Add to GitHub repository secrets
#    Navigate: https://github.com/terrylica/binance-futures-availability/settings/secrets/actions
#    Add secret: DOPPLER_TOKEN = <service_token>

# 3. Verify Doppler secrets
doppler secrets --project notifications --config prd | grep PUSHOVER
```

**Validation**:

- GitHub secret `DOPPLER_TOKEN` exists
- Doppler secrets `PUSHOVER_API_TOKEN` and `PUSHOVER_USER_KEY` exist

### Phase 2: Doppler Integration (15 minutes)

**Status**: Pending

**Files to Modify**:

1. `.github/workflows/update-database.yml` (line ~50, after checkout)

**Implementation**:

Add Doppler secrets fetch step after repository checkout:

```yaml
- name: Fetch secrets from Doppler
  uses: doppler/cli-action@v3
  with:
    install-only: true

- name: Load Doppler secrets
  run: |
    doppler secrets download --no-file --format env-no-quotes >> $GITHUB_ENV
  env:
    DOPPLER_TOKEN: ${{ secrets.DOPPLER_TOKEN }}
    DOPPLER_PROJECT: notifications
    DOPPLER_CONFIG: prd
```

**Rationale**:

- Centralized secret management (single source of truth)
- Secrets automatically injected as environment variables
- Shared across repositories when needed
- ADR-0022 decision: Doppler integration over manual GitHub secrets

**Validation**:

```bash
# Validate YAML syntax
yamllint .github/workflows/update-database.yml

# Check workflow locally (if possible)
act workflow_dispatch -W .github/workflows/update-database.yml
```

### Phase 3: Pushover Notification Step (45 minutes)

**Status**: Pending

**Files to Modify**:

1. `.github/workflows/update-database.yml` (line ~543, end of NOTIFY section)

**Implementation**:

Add notification step at end of workflow (after GitHub Actions summary):

```yaml
# ============================================================================
# NOTIFY: Send Pushover notification
# ============================================================================

- name: Send Pushover Notification
  if: always()  # Run on all statuses
  env:
    JOB_STATUS: ${{ job.status }}
    WORKFLOW_NAME: ${{ github.workflow }}
    LATEST_DATE: ${{ steps.stats.outputs.latest_date || 'N/A' }}
    TOTAL_RECORDS: ${{ steps.stats.outputs.total_records || 'N/A' }}
    AVAILABLE_COUNT: ${{ steps.stats.outputs.available_count || 'N/A' }}
    UNAVAILABLE_COUNT: ${{ steps.stats.outputs.unavailable_count || 'N/A' }}
    VALIDATION_STATUS: ${{ steps.validate.outputs.validation_passed == 'true' && 'Passed' || 'Failed' }}
    RANKINGS_GENERATED: ${{ steps.generate_rankings.outputs.rankings_generated || 'false' }}
    RANKINGS_ROWS: ${{ steps.generate_rankings.outputs.rankings_rows || '0' }}
    RUN_URL: https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}
    TRIGGER: ${{ github.event_name }}
  run: |
    # Determine notification details based on job status
    if [ "$JOB_STATUS" = "success" ]; then
      TITLE="✅ Binance Futures DB Updated"
      SOUND="toy_story"

      if [ "$RANKINGS_GENERATED" = "true" ]; then
        RANKINGS_STATUS="✅ Generated ($RANKINGS_ROWS symbols)"
      else
        RANKINGS_STATUS="⚠️ Failed (non-blocking)"
      fi

      MESSAGE="Database Update: $LATEST_DATE

    📊 Stats:
    - Records: $TOTAL_RECORDS
    - Available: $AVAILABLE_COUNT
    - Unavailable: $UNAVAILABLE_COUNT
    - Validation: $VALIDATION_STATUS

    📈 Volume Rankings: $RANKINGS_STATUS

    🔗 View: $RUN_URL"

    elif [ "$JOB_STATUS" = "failure" ]; then
      TITLE="❌ DB Update Failed"
      SOUND="alien"
      MESSAGE="Workflow Failed

    Status: $VALIDATION_STATUS
    Latest Date: $LATEST_DATE
    Trigger: $TRIGGER

    🔗 Check logs: $RUN_URL"

    else
      # Cancelled
      TITLE="⚠️ DB Update Cancelled"
      SOUND="mechanical"
      MESSAGE="Workflow was manually cancelled

    Trigger: $TRIGGER

    🔗 View: $RUN_URL"
    fi

    # Send Pushover notification
    HTTP_CODE=$(curl -s -w "%{http_code}" -o /tmp/pushover_response.json \
      --form-string "token=$PUSHOVER_API_TOKEN" \
      --form-string "user=$PUSHOVER_USER_KEY" \
      --form-string "title=$TITLE" \
      --form-string "message=$MESSAGE" \
      --form-string "sound=$SOUND" \
      --form-string "priority=0" \
      https://api.pushover.net/1/messages.json)

    if [ "$HTTP_CODE" -eq 200 ]; then
      echo "✅ Pushover notification sent: $TITLE"
      cat /tmp/pushover_response.json
    else
      echo "⚠️ Pushover notification failed (HTTP $HTTP_CODE)"
      cat /tmp/pushover_response.json
      # Non-blocking: don't fail workflow if notification fails
      exit 0
    fi
```

**Notification Content by Status**:

1. **Success**: Database stats, validation status, rankings status, run URL
2. **Failure**: Error context, validation status, trigger type, logs URL
3. **Cancelled**: Cancellation notice, trigger type, run URL

**Error Handling**:

- Non-blocking: Notification failure doesn't fail workflow (per ADR-0003 policy exception)
- Defensive defaults: Use `|| 'N/A'` for stats that may not exist
- HTTP status check: Log response for debugging

**Validation**:

```bash
# Validate YAML syntax
yamllint .github/workflows/update-database.yml

# Validate GitHub expressions
# (done automatically by GitHub Actions validation)
```

### Phase 4: Testing (30 minutes)

**Status**: Pending

**Test Scenarios**:

1. **Success Test**: Trigger workflow manually, verify success notification
2. **Failure Test**: Intentionally break workflow (e.g., invalid DB_PATH), verify failure notification
3. **Cancelled Test**: Manually cancel running workflow, verify cancelled notification
4. **Stats Test**: Confirm all database stats appear in notification (latest_date, records, counts)

**Test Commands**:

```bash
# 1. Trigger manual workflow run
gh workflow run update-database.yml

# 2. Monitor workflow
gh run list --workflow=update-database.yml --limit 1

# 3. Check notification on phone/desktop

# 4. Verify notification content matches expected format
```

**Validation Checklist**:

- [ ] Notification arrives within 5 seconds of workflow completion
- [ ] Title format correct (✅/❌/⚠️ prefix)
- [ ] Database stats included (latest_date, total_records, available_count, unavailable_count)
- [ ] Validation status shown
- [ ] Volume rankings status shown
- [ ] Run URL clickable and correct
- [ ] Sound appropriate for status (toy_story/alien/mechanical)
- [ ] Workflow passes even if notification step fails

### Phase 5: Documentation (15 minutes)

**Status**: Pending

**Files to Modify**:

1. `CHANGELOG.md` - Add feature entry
2. `CLAUDE.md` - Update automation section
3. `README.md` - Mention Pushover notifications in Quick Start

**Implementation**:

```markdown
# CHANGELOG.md
## [Unreleased]

### Added

- **notifications:** add Pushover workflow notifications (ADR-0022) ([commit-hash])

**Feature**: Real-time Pushover notifications on all workflow statuses (success/failure/cancelled)

**Implementation**:
- Doppler SecretOps integration for centralized secret management
- Custom curl-based notification with rich database statistics
- Conditional formatting based on job status
- Non-blocking error handling

**Impact**:
- Instant workflow visibility (no manual GitHub UI checks)
- 30 hours/year time savings (5 min/day monitoring eliminated)
- Faster incident response (immediate failure detection)
```

**Validation**:

- CHANGELOG entry follows conventional commit format
- Documentation mentions Doppler + Pushover setup
- Links to ADR-0022 included

## Task List

This task list must stay synchronized with the plan above and the ADR.

### Setup Tasks

- [ ] Verify Doppler "notifications" project has PUSHOVER_API_TOKEN and PUSHOVER_USER_KEY
- [ ] Create Doppler service token for GitHub Actions
- [ ] Add DOPPLER_TOKEN to GitHub repository secrets

### Implementation Tasks

- [ ] Add Doppler secrets fetch step to workflow (after checkout, line ~50)
- [ ] Add Pushover notification step to workflow (end of NOTIFY section, line ~543)
- [ ] Implement conditional notification formatting (success/failure/cancelled)
- [ ] Add defensive defaults for stats that may not exist
- [ ] Add non-blocking error handling (notification failure doesn't fail workflow)

### Validation Tasks

- [ ] Validate workflow YAML syntax (yamllint)
- [ ] Test success notification (manual workflow trigger)
- [ ] Test failure notification (intentionally break workflow)
- [ ] Test cancelled notification (manually cancel running workflow)
- [ ] Verify all database stats appear in notification
- [ ] Confirm notification arrives within 5 seconds
- [ ] Verify workflow passes even if notification fails

### Documentation Tasks

- [ ] Update CHANGELOG.md with feature entry
- [ ] Update CLAUDE.md automation section
- [ ] Update README.md Quick Start with Pushover mention
- [ ] Create conventional commit message
- [ ] Use semantic-release skill for versioning

## Progress Log

Track execution here as work progresses:

### 2025-11-22 [HH:MM] - Plan Created

- ✅ ADR-0022 created
- ✅ Implementation plan created (this file)
- ⏳ Ready to begin Phase 1 (Secret Setup)

### 2025-11-22 [HH:MM] - Phase 1 Started

TBD

## SLO Compliance

Per ADR-0000, focus on 4 dimensions (not speed/performance/security):

### Availability

- ✅ **Target**: Notifications arrive on 95%+ of workflow runs
- **Measurement**: Monitor Pushover notification success rate
- **Non-blocking**: Notification failure doesn't fail workflow

### Correctness

- ✅ **Target**: Notification content accurate (stats match database)
- **Measurement**: Manual verification during testing phase
- **Validation**: Compare notification stats with GitHub Actions summary

### Observability

- ✅ **Target**: Instant workflow visibility without GitHub UI checks
- **Measurement**: User no longer needs to manually check workflow status
- **Feedback Loop**: Pushover notification provides complete context

### Maintainability

- ✅ **Target**: Centralized secret management (Doppler)
- **Measurement**: No manual GitHub secret updates needed
- **Documentation**: ADR-0022 + this plan + CHANGELOG entry

## Error Handling Strategy

Per ADR-0003 (strict raise policy) with exception for notifications:

- **Doppler Failure**: Raise and fail workflow (secrets critical)
- **Pushover API Failure**: Log warning, exit 0 (non-blocking)
- **Missing Stats**: Defensive defaults (`|| 'N/A'`)
- **Network Timeout**: curl default timeout (exit 0 on failure)

**Rationale**: Notification is observability enhancement, not critical data operation. Workflow success should reflect data quality, not notification delivery.

## Dependencies

**External Services**:

- Doppler SecretOps Platform (https://github.com/settings/installations/88898750)
- Pushover API (https://pushover.net/api)

**GitHub Actions**:

- `doppler/cli-action@v3` - Doppler CLI installation

**Secrets Required**:

1. GitHub repository secret: `DOPPLER_TOKEN`
2. Doppler secrets: `PUSHOVER_API_TOKEN`, `PUSHOVER_USER_KEY`

## Rollback Plan

If implementation causes issues:

1. **Immediate**: Comment out Pushover notification step (workflow still functional)
2. **Quick**: Remove Doppler fetch step + Pushover step (revert to previous state)
3. **Clean**: Revert entire commit via git revert

Workflow remains functional throughout - notification is additive, not critical path.

## Future Enhancements

Deferred to future sprints:

- Notification batching for multiple workflow runs
- Custom notification priorities based on failure type
- Slack/Discord integration for team notifications
- Pushover emergency priority for critical failures
- Notification analytics dashboard
