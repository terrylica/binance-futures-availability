#!/bin/bash
# Monitor GitHub Actions workflow and send Pushover notification on completion
#
# Usage: ./monitor_workflow.sh <run_id>
# Example: ./monitor_workflow.sh 19584202568

set -euo pipefail

RUN_ID="${1:-}"

if [[ -z "$RUN_ID" ]]; then
    echo "Usage: $0 <run_id>"
    echo "Example: $0 19584202568"
    echo ""
    echo "Get latest run ID:"
    echo "  gh run list --workflow=update-database.yml --limit 1 --json databaseId -q '.[0].databaseId'"
    exit 1
fi

echo "🔍 Monitoring workflow run: $RUN_ID"
echo "⏳ Checking status every 30 seconds..."
echo ""

POLL_INTERVAL=30
MAX_WAIT=1800  # 30 minutes
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Get run status
    RUN_DATA=$(gh run view "$RUN_ID" --json status,conclusion,displayTitle,createdAt,startedAt,updatedAt)

    STATUS=$(echo "$RUN_DATA" | jq -r '.status')
    CONCLUSION=$(echo "$RUN_DATA" | jq -r '.conclusion // "none"')
    TITLE=$(echo "$RUN_DATA" | jq -r '.displayTitle')

    echo "[$(date '+%H:%M:%S')] Status: $STATUS | Conclusion: $CONCLUSION"

    # Check if completed
    if [[ "$STATUS" == "completed" ]]; then
        echo ""
        echo "✅ Workflow completed!"
        echo ""

        # Get final details
        CREATED_AT=$(echo "$RUN_DATA" | jq -r '.createdAt')
        STARTED_AT=$(echo "$RUN_DATA" | jq -r '.startedAt')
        UPDATED_AT=$(echo "$RUN_DATA" | jq -r '.updatedAt')

        # Prepare notification
        if [[ "$CONCLUSION" == "success" ]]; then
            NOTIFICATION_TITLE="✅ Workflow Succeeded"
            NOTIFICATION_MESSAGE="Binance Futures DB Update

🔧 $TITLE
✅ Status: $CONCLUSION
🕐 Started: $STARTED_AT
🕐 Completed: $UPDATED_AT

Run ID: $RUN_ID
View: https://github.com/terrylica/binance-futures-availability/actions/runs/$RUN_ID"
            SOUND="toy_story"
        else
            NOTIFICATION_TITLE="❌ Workflow Failed"
            NOTIFICATION_MESSAGE="Binance Futures DB Update

🔧 $TITLE
❌ Status: $CONCLUSION
🕐 Started: $STARTED_AT
🕐 Completed: $UPDATED_AT

Run ID: $RUN_ID
View: https://github.com/terrylica/binance-futures-availability/actions/runs/$RUN_ID

Check logs for details."
            SOUND="alien"
        fi

        # Send Pushover notification
        if command -v pushover-notify &> /dev/null; then
            echo "📤 Sending Pushover notification..."
            pushover-notify "$NOTIFICATION_TITLE" "$NOTIFICATION_MESSAGE" "" "$SOUND"
            echo "✅ Notification sent!"
        else
            echo "⚠️  pushover-notify not found in PATH"
            echo "   Install from: ~/.claude/tools/notifications/pushover-notify"
        fi

        # Print summary
        echo ""
        echo "=================================================="
        echo "WORKFLOW SUMMARY"
        echo "=================================================="
        echo "Run ID: $RUN_ID"
        echo "Title: $TITLE"
        echo "Conclusion: $CONCLUSION"
        echo "Duration: $(( ($(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$UPDATED_AT" +%s) - $(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$STARTED_AT" +%s)) / 60 )) minutes"
        echo "View: https://github.com/terrylica/binance-futures-availability/actions/runs/$RUN_ID"
        echo "=================================================="

        exit 0
    fi

    # Wait before next poll
    sleep $POLL_INTERVAL
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

echo ""
echo "⏰ Timeout: Workflow still running after $MAX_WAIT seconds"
echo "   Check status manually: gh run view $RUN_ID"
exit 1
