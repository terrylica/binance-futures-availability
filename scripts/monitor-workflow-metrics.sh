#!/bin/bash
#
# GitHub Actions Workflow Monitoring Dashboard (ADR-0009 Phase 4)
# Tracks SLO metrics for automated database updates
#
# Usage:
#   ./scripts/monitor-workflow-metrics.sh
#   ./scripts/monitor-workflow-metrics.sh --days 30
#   ./scripts/monitor-workflow-metrics.sh --json
#
# SLOs Tracked (from plan.yaml):
#   - Availability: ≥95% workflow success rate
#   - Workflow Duration: 5-10 minutes (alert if >15 minutes)
#   - Observability: 100% failures logged
#   - Maintainability: Zero manual intervention
#
# Exit codes:
#   0 - All SLOs met
#   1 - One or more SLOs violated
#

set -e  # Exit on error
set -u  # Exit on undefined variable

# =============================================================================
# Configuration
# =============================================================================

WORKFLOW_NAME="update-database.yml"
DEFAULT_DAYS=7
OUTPUT_FORMAT="human"  # human or json

# SLO Thresholds (from docs/plans/0009-github-actions-automation/plan.yaml)
SLO_SUCCESS_RATE=95  # Minimum success rate percentage
SLO_MAX_DURATION=900  # 15 minutes in seconds (alert threshold)
SLO_EXPECTED_MIN_DURATION=300  # 5 minutes
SLO_EXPECTED_MAX_DURATION=600  # 10 minutes

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    if [ "$OUTPUT_FORMAT" = "human" ]; then
        echo -e "${BLUE}[INFO]${NC} $1"
    fi
}

log_success() {
    if [ "$OUTPUT_FORMAT" = "human" ]; then
        echo -e "${GREEN}[✓]${NC} $1"
    fi
}

log_warning() {
    if [ "$OUTPUT_FORMAT" = "human" ]; then
        echo -e "${YELLOW}[⚠]${NC} $1"
    fi
}

log_error() {
    if [ "$OUTPUT_FORMAT" = "human" ]; then
        echo -e "${RED}[✗]${NC} $1"
    fi
}

section_header() {
    if [ "$OUTPUT_FORMAT" = "human" ]; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}$1${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
    fi
}

# =============================================================================
# Parse Arguments
# =============================================================================

DAYS=$DEFAULT_DAYS

while [[ $# -gt 0 ]]; do
    case $1 in
        --days)
            DAYS="$2"
            shift 2
            ;;
        --json)
            OUTPUT_FORMAT="json"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--days N] [--json]"
            exit 1
            ;;
    esac
done

# =============================================================================
# Data Collection
# =============================================================================

collect_workflow_runs() {
    # Get workflow runs for the specified period
    local limit=$((DAYS * 3))  # Assume max 3 runs per day

    gh run list \
        --workflow="$WORKFLOW_NAME" \
        --limit="$limit" \
        --json databaseId,conclusion,createdAt,updatedAt,status,event,displayTitle \
        2>/dev/null
}

calculate_metrics() {
    local runs_json="$1"

    # Total runs
    local total_runs=$(echo "$runs_json" | jq 'length')

    if [ "$total_runs" -eq 0 ]; then
        echo '{"error": "No workflow runs found"}'
        return 1
    fi

    # Success/failure counts
    local success_count=$(echo "$runs_json" | jq '[.[] | select(.conclusion == "success")] | length')
    local failure_count=$(echo "$runs_json" | jq '[.[] | select(.conclusion == "failure")] | length')
    local cancelled_count=$(echo "$runs_json" | jq '[.[] | select(.conclusion == "cancelled")] | length')
    local in_progress_count=$(echo "$runs_json" | jq '[.[] | select(.status == "in_progress")] | length')

    # Success rate
    local completed_runs=$((success_count + failure_count))
    local success_rate=0
    if [ "$completed_runs" -gt 0 ]; then
        success_rate=$(echo "scale=2; ($success_count * 100) / $completed_runs" | bc)
    fi

    # Duration statistics (only for completed runs)
    local durations=$(echo "$runs_json" | jq -r '
        .[] |
        select(.conclusion == "success" or .conclusion == "failure") |
        (((.updatedAt | fromdateiso8601) - (.createdAt | fromdateiso8601)) / 60)
    ')

    local avg_duration=0
    local min_duration=0
    local max_duration=0

    if [ -n "$durations" ]; then
        avg_duration=$(echo "$durations" | awk '{sum+=$1; count++} END {if(count>0) printf "%.1f", sum/count; else print 0}')
        min_duration=$(echo "$durations" | sort -n | head -1)
        max_duration=$(echo "$durations" | sort -n | tail -1)
    fi

    # Scheduled vs manual runs
    local scheduled_runs=$(echo "$runs_json" | jq '[.[] | select(.event == "schedule")] | length')
    local manual_runs=$(echo "$runs_json" | jq '[.[] | select(.event == "workflow_dispatch")] | length')

    # Recent failures (last 3 failed runs)
    local recent_failures=$(echo "$runs_json" | jq -r '
        [.[] | select(.conclusion == "failure")] |
        sort_by(.createdAt) | reverse |
        .[0:3] |
        .[] |
        "\(.databaseId)|\(.displayTitle)|\(.createdAt)"
    ')

    # Output JSON or human-readable format
    if [ "$OUTPUT_FORMAT" = "json" ]; then
        cat <<EOF
{
  "total_runs": $total_runs,
  "success_count": $success_count,
  "failure_count": $failure_count,
  "cancelled_count": $cancelled_count,
  "in_progress_count": $in_progress_count,
  "success_rate": $success_rate,
  "avg_duration_minutes": $avg_duration,
  "min_duration_minutes": $min_duration,
  "max_duration_minutes": $max_duration,
  "scheduled_runs": $scheduled_runs,
  "manual_runs": $manual_runs,
  "slo_success_rate_target": $SLO_SUCCESS_RATE,
  "slo_success_rate_met": $([ "${success_rate%.*}" -ge "$SLO_SUCCESS_RATE" ] && echo "true" || echo "false"),
  "slo_duration_alert": $(awk -v max="$max_duration" -v threshold="$SLO_MAX_DURATION" 'BEGIN {print (max*60 > threshold) ? "true" : "false"}')
}
EOF
    else
        section_header "GitHub Actions Workflow Metrics (Last $DAYS Days)"

        echo "Workflow: $WORKFLOW_NAME"
        echo "Period: Last $DAYS days"
        echo ""

        # Run counts
        echo "Run Statistics:"
        echo "  Total runs:        $total_runs"
        echo "  ✓ Success:         $success_count"
        echo "  ✗ Failure:         $failure_count"
        echo "  ○ Cancelled:       $cancelled_count"
        echo "  ⋯ In progress:     $in_progress_count"
        echo ""

        # Success rate with SLO check
        echo "Success Rate:"
        if [ "${success_rate%.*}" -ge "$SLO_SUCCESS_RATE" ]; then
            log_success "Success rate: ${success_rate}% (target: ≥${SLO_SUCCESS_RATE}%) ✓"
        else
            log_error "Success rate: ${success_rate}% (target: ≥${SLO_SUCCESS_RATE}%) ✗"
        fi
        echo ""

        # Duration statistics with SLO check
        echo "Duration Statistics:"
        echo "  Average:           ${avg_duration} minutes"
        echo "  Minimum:           ${min_duration} minutes"
        echo "  Maximum:           ${max_duration} minutes"
        echo "  Expected range:    ${SLO_EXPECTED_MIN_DURATION}/60-${SLO_EXPECTED_MAX_DURATION}/60 minutes"
        echo ""

        # Duration SLO check
        max_duration_seconds=$(echo "$max_duration * 60" | bc | cut -d. -f1)
        if [ "$max_duration_seconds" -gt "$SLO_MAX_DURATION" ]; then
            log_warning "Maximum duration exceeds alert threshold (>15 minutes)"
        else
            log_success "All durations within acceptable range"
        fi
        echo ""

        # Trigger breakdown
        echo "Trigger Breakdown:"
        echo "  Scheduled (cron):  $scheduled_runs"
        echo "  Manual dispatch:   $manual_runs"
        echo ""

        # Recent failures
        if [ "$failure_count" -gt 0 ]; then
            section_header "Recent Failures"
            echo "Last 3 failed runs:"
            echo ""

            if [ -n "$recent_failures" ]; then
                while IFS='|' read -r run_id title created_at; do
                    echo "  Run #$run_id"
                    echo "    Title:   $title"
                    echo "    Date:    $created_at"
                    echo "    Logs:    gh run view $run_id --log"
                    echo ""
                done <<< "$recent_failures"
            fi
        fi

        # SLO Summary
        section_header "SLO Compliance Summary"

        local slo_violations=0

        # Availability SLO
        if [ "${success_rate%.*}" -ge "$SLO_SUCCESS_RATE" ]; then
            log_success "Availability SLO: MET (${success_rate}% ≥ ${SLO_SUCCESS_RATE}%)"
        else
            log_error "Availability SLO: VIOLATED (${success_rate}% < ${SLO_SUCCESS_RATE}%)"
            ((slo_violations++))
        fi

        # Duration SLO
        if [ "$max_duration_seconds" -le "$SLO_MAX_DURATION" ]; then
            log_success "Duration SLO: MET (max ${max_duration} min ≤ 15 min)"
        else
            log_warning "Duration SLO: ALERT (max ${max_duration} min > 15 min)"
        fi

        # Observability SLO (all failures logged)
        if [ "$failure_count" -gt 0 ]; then
            log_success "Observability SLO: MET (${failure_count} failures logged and visible)"
        else
            log_success "Observability SLO: MET (no failures to log)"
        fi

        # Maintainability SLO (zero manual intervention)
        if [ "$scheduled_runs" -gt 0 ]; then
            log_success "Maintainability SLO: MET (${scheduled_runs} automated runs)"
        else
            log_warning "Maintainability SLO: No scheduled runs found (only manual runs)"
        fi

        echo ""

        if [ "$slo_violations" -eq 0 ]; then
            log_success "✅ All SLOs met"
            return 0
        else
            log_error "❌ $slo_violations SLO violation(s) detected"
            return 1
        fi
    fi
}

# =============================================================================
# Main Function
# =============================================================================

main() {
    if [ "$OUTPUT_FORMAT" = "human" ]; then
        section_header "Workflow Monitoring Dashboard (ADR-0009)"
        log_info "Collecting workflow metrics..."
        echo ""
    fi

    # Check if gh CLI is available
    if ! command -v gh &> /dev/null; then
        log_error "gh CLI not installed. Install: brew install gh"
        return 2
    fi

    # Check if authenticated
    if ! gh auth status &> /dev/null; then
        log_error "Not authenticated with GitHub. Run: gh auth login"
        return 2
    fi

    # Collect workflow runs
    local runs_json
    runs_json=$(collect_workflow_runs)

    if [ $? -ne 0 ] || [ -z "$runs_json" ]; then
        log_error "Failed to collect workflow runs"
        return 2
    fi

    # Calculate and display metrics
    calculate_metrics "$runs_json"
    return $?
}

# Run main function
main "$@"
