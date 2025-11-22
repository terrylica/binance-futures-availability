# ADR-0022: Pushover Workflow Notifications

**Status**: Accepted

**Date**: 2025-11-22

**Deciders**: Data Pipeline Engineer, DevOps Engineer

**Technical Story**: Add real-time Pushover notifications to GitHub Actions workflow delivering instant workflow status visibility (success/failure/cancelled) with comprehensive database statistics, eliminating manual workflow monitoring overhead.

## Context and Problem Statement

Current workflow monitoring approach (GitHub Actions):

- **Manual Monitoring**: User must navigate to GitHub Actions UI to check workflow status
- **No Real-time Alerts**: Scheduled 3AM UTC runs complete silently, requiring manual verification
- **Local Script Exists**: `scripts/operations/monitor_workflow.sh` provides Pushover notifications but requires manual execution
- **Limited Observability**: No instant feedback on workflow failures during critical operations

While functional, this approach creates **operational friction**:

1. **No Instant Feedback**: User discovers failures hours later when checking GitHub manually
2. **Inconsistent Monitoring**: Local script provides great UX but requires manual trigger
3. **Context Switching**: Must open browser, navigate to Actions tab, inspect logs
4. **Delayed Incident Response**: Failures during scheduled runs go unnoticed until next manual check

User requirement: *"When the CI/CD running on GitHub after successful running or even after whatever status where I get pushed over a notification at the end."*

## Decision Drivers

- **Availability SLO**: Instant notification of workflow failures enables immediate incident response
- **Observability SLO**: Real-time status visibility without manual GitHub UI checks
- **Maintainability SLO**: Consistent notification format across local + CI workflows
- **Correctness SLO**: Notifications include validation status to confirm data quality
- **User Experience**: Eliminate manual workflow monitoring overhead
- **Zero Infrastructure Cost**: Leverages existing Pushover account + GitHub Actions

## Considered Options

### Option 1: Status Quo (Manual Monitoring)

Continue current approach:

- User manually checks GitHub Actions UI for workflow status
- Local `monitor_workflow.sh` script available but requires manual execution
- No automated notifications

**Pros**:

- Zero effort
- Current approach functional
- No additional dependencies

**Cons**:

- **Manual Overhead**: Requires daily GitHub UI checks
- **Delayed Incident Detection**: Failures discovered hours/days later
- **Inconsistent UX**: Local script provides notifications, CI does not
- **Context Switching**: Must open browser to check status

### Option 2: GitHub Email Notifications

Use GitHub's built-in workflow failure emails:

**Pros**:

- Zero configuration (enabled by default)
- No external dependencies

**Cons**:

- **Email Fatigue**: Buried in inbox, low priority
- **No Success Notifications**: Only notifies on failure
- **Limited Context**: Generic "workflow failed" message
- **No Database Stats**: Doesn't include validation status, record counts, etc.

### Option 3: Pushover Notifications via Custom Script (CHOSEN)

Add Pushover notification step to workflow using custom curl script:

1. **Doppler Integration**: Sync secrets from "notifications" project using `doppler-labs/secrets-fetch-action`
2. **Notification Step**: Run on all statuses (`if: always()`) with conditional formatting
3. **Rich Context**: Include database stats, validation status, rankings status, run details

**Pros**:

- **Instant Feedback**: Notifications arrive on phone/desktop immediately
- **All Statuses**: Success, failure, cancelled all trigger notifications
- **Rich Context**: Includes latest_date, record counts, validation status, rankings status
- **Consistent UX**: Matches local monitoring script format
- **Centralized Secrets**: Doppler manages credentials, shared across repos
- **Full Control**: Custom curl allows complete message customization

**Cons**:

- **Additional Step**: Adds ~2 seconds to workflow runtime
- **External Dependency**: Requires Pushover account (already in use)
- **Secret Management**: Requires DOPPLER_TOKEN in GitHub secrets

**ROI Analysis**:

- **Time Saved**: ~5 min/day × 365 days = 30 hours/year (no manual checks)
- **Implementation**: ~2 hours (ADR + implementation + testing)
- **ROI**: 1,500% (30 hours saved / 2 hours invested)

### Option 4: Pre-built GitHub Action

Use `desiderati/github-action-pushover@v1`:

**Pros**:

- Minimal YAML (3 lines)
- Maintained action

**Cons**:

- **Limited Customization**: No database stats, validation status
- **Third-party Dependency**: Relies on external action maintenance
- **Inconsistent Format**: Doesn't match local monitoring script

## Decision Outcome

**Chosen Option**: Option 3 (Pushover Notifications via Custom Script)

**Rationale**:

1. **User Requirement**: Explicit request for Pushover notifications on all workflow statuses
2. **Proven Format**: Local monitoring script already demonstrates value
3. **Rich Context**: Database stats + validation status enable immediate assessment
4. **Centralized Secrets**: Doppler integration aligns with existing secret management
5. **High ROI**: 1,500% return (30 hours/year saved, 2 hours implementation)

## Implementation Details

### Notification Content by Status

**Success** (job.status == 'success'):

```
Title: ✅ Binance Futures DB Updated
Sound: toy_story

Message:
Database Update: 2025-11-21

📊 Stats:
- Records: 1,606,500
- Available: 485,341
- Unavailable: 1,121,159
- Validation: Passed

📈 Volume Rankings: ✅ Generated (327 symbols)

🔗 View: https://github.com/terrylica/binance-futures-availability/actions/runs/19589708175
```

**Failure** (job.status == 'failure'):

```
Title: ❌ DB Update Failed
Sound: alien

Message:
Workflow Failed

Status: Validation Failed
Latest Date: 2025-11-21

🔗 Check logs: https://github.com/terrylica/binance-futures-availability/actions/runs/...
```

**Cancelled** (job.status == 'cancelled'):

```
Title: ⚠️ DB Update Cancelled
Sound: mechanical

Message:
Workflow was manually cancelled

🔗 View: https://github.com/terrylica/binance-futures-availability/actions/runs/...
```

### Required Secrets

**GitHub Repository Secret**:

- `DOPPLER_TOKEN`: Service token for Doppler "notifications" project

**Doppler Secrets** (in "notifications" project):

- `PUSHOVER_API_TOKEN`: Application API token from https://pushover.net/apps
- `PUSHOVER_USER_KEY`: User key from Pushover dashboard

### Workflow Integration Points

1. **Doppler Sync** (after checkout, line ~50):
   - Fetches all secrets from Doppler "notifications" project
   - Injects as environment variables for subsequent steps

2. **Pushover Notification** (end of workflow, line ~543):
   - Runs with `if: always()` to handle all statuses
   - Uses defensive defaults (`|| 'N/A'`) for stats that may not exist
   - Conditional formatting based on `${{ job.status }}`

### Error Handling

Per ADR-0003 (strict error policy):

- **Notification Failure**: Non-blocking (workflow marked success even if notification fails)
- **Missing Stats**: Defensive defaults prevent expression errors
- **Doppler Failure**: Workflow fails fast if DOPPLER_TOKEN invalid

## Consequences

### Positive

- **Instant Visibility**: Workflow status notifications arrive within seconds
- **Reduced Manual Overhead**: No daily GitHub UI checks required
- **Faster Incident Response**: Failures detected immediately, not hours later
- **Rich Context**: Database stats enable immediate quality assessment
- **Consistent UX**: Matches local monitoring script format
- **Availability SLO Improvement**: Faster detection → faster recovery

### Negative

- **External Dependency**: Requires Pushover account (already in use)
- **Notification Volume**: ~30 notifications/month (well within Pushover free tier: 10,000/month)
- **Slight Workflow Overhead**: +2 seconds per run (Doppler sync + curl)

### Risks

- **Doppler Outage**: If Doppler unavailable, workflow fails (acceptable per ADR-0003)
- **Pushover Rate Limits**: Free tier supports 10,000 msg/month, we use ~30/month (3% utilization)
- **Secret Rotation**: DOPPLER_TOKEN rotation requires GitHub secret update

### Mitigation

- **Doppler SLA**: 99.99% uptime (better than GitHub Actions 99.9%)
- **Rate Limits**: Monitoring shows 3% utilization, no risk
- **Secret Rotation**: Documented in plan, quarterly rotation recommended

## Compliance

### SLOs (ADR-0000)

- **Availability**: ✅ Faster incident detection improves recovery time
- **Correctness**: ✅ Notifications include validation status
- **Observability**: ✅ Real-time workflow visibility
- **Maintainability**: ✅ Centralized secret management

### Error Handling (ADR-0003)

- ✅ Doppler failures raise immediately (strict policy)
- ✅ Notification failures non-blocking (don't fail workflow on curl error)
- ✅ Structured logging for notification step

## References

- **Local Monitoring Script**: `scripts/operations/monitor_workflow.sh`
- **Doppler GitHub Integration**: https://github.com/settings/installations/88898750
- **Pushover API**: https://pushover.net/api
- **Related ADRs**: ADR-0003 (error handling), ADR-0009 (GitHub Actions automation)
- **Implementation Plan**: `docs/development/plan/0022-pushover-workflow-notifications/plan.md`

## Notes

User feedback driving decision:

> "When the CI/CD running on GitHub after successful running or even after whatever status where I get pushed over a notification at the end."

Selected preferences:

- **Notify When**: Success, Failure, Cancelled (all statuses)
- **Secret Management**: Doppler integration (automated sync)
- **Implementation**: Custom curl script (full control over content)
- **Notification Content**: Database statistics, validation status, volume rankings status, run details
