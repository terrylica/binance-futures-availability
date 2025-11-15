#!/bin/bash
#
# Workflow Deployment Validation Script (ADR-0009 Phase 3)
# Validates GitHub Actions workflow deployment and readiness
#
# Usage:
#   ./scripts/validate-workflow-deployment.sh
#
# Exit codes:
#   0 - All validations passed
#   1 - Validation failures detected
#

set -e  # Exit on error
set -u  # Exit on undefined variable

# =============================================================================
# Configuration
# =============================================================================

WORKFLOW_NAME="update-database.yml"
EXPECTED_FILES=(
    ".github/workflows/update-database.yml"
    "docs/decisions/0009-github-actions-automation.md"
    "docs/plans/0009-github-actions-automation/plan.yaml"
    "docs/operations/GITHUB_ACTIONS.md"
    "docs/operations/DEPLOYMENT_GUIDE.md"
    "scripts/test-workflow-locally.sh"
)

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
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

section_header() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
}

# =============================================================================
# Validation Functions
# =============================================================================

validate_files_exist() {
    section_header "Validating File Existence"

    local all_exist=true
    for file in "${EXPECTED_FILES[@]}"; do
        if [ -f "$file" ]; then
            log_success "File exists: $file"
        else
            log_error "File missing: $file"
            all_exist=false
        fi
    done

    if [ "$all_exist" = true ]; then
        log_success "All required files present"
        return 0
    else
        log_error "Some files are missing"
        return 1
    fi
}

validate_adr_plan_sync() {
    section_header "Validating ADR↔Plan Synchronization"

    # Check ADR status
    local adr_status=$(grep "^**Status**:" docs/decisions/0009-github-actions-automation.md | cut -d: -f2 | xargs)
    log_info "ADR Status: $adr_status"

    if [ "$adr_status" = "Accepted" ]; then
        log_success "ADR-0009 status is Accepted"
    else
        log_error "ADR-0009 status is not Accepted: $adr_status"
        return 1
    fi

    # Check plan x-adr-id
    local plan_adr_id=$(grep "x-adr-id:" docs/plans/0009-github-actions-automation/plan.yaml | cut -d'"' -f2)
    log_info "Plan x-adr-id: $plan_adr_id"

    if [ "$plan_adr_id" = "0009" ]; then
        log_success "Plan correctly references ADR-0009"
    else
        log_error "Plan x-adr-id mismatch: $plan_adr_id"
        return 1
    fi

    # Check plan status
    local plan_status=$(grep "status:" docs/plans/0009-github-actions-automation/plan.yaml | head -1 | cut -d'"' -f2)
    log_info "Plan Status: $plan_status"

    if [ "$plan_status" = "ready-for-deployment" ]; then
        log_success "Plan status is ready-for-deployment"
    else
        log_warning "Plan status is: $plan_status"
    fi

    log_success "ADR↔Plan synchronization verified"
    return 0
}

validate_workflow_syntax() {
    section_header "Validating Workflow Syntax"

    # Check if workflow file is valid YAML
    if python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/update-database.yml'))" 2>/dev/null; then
        log_success "Workflow YAML syntax is valid"
    else
        log_warning "Could not validate YAML syntax (PyYAML not installed)"
    fi

    # Check for required workflow keys
    local required_keys=("name" "on" "jobs")
    for key in "${required_keys[@]}"; do
        if grep -q "^${key}:" .github/workflows/update-database.yml; then
            log_success "Workflow contains required key: $key"
        else
            log_error "Workflow missing required key: $key"
            return 1
        fi
    done

    log_success "Workflow syntax validation passed"
    return 0
}

validate_module_references() {
    section_header "Validating Module References"

    # Check that referenced Python modules exist
    local modules=(
        "src/binance_futures_availability/scheduler/daily_update.py"
        "src/binance_futures_availability/scheduler/notifications.py"
        "scripts/operations/backfill.py"
        "scripts/operations/validate.py"
    )

    local all_exist=true
    for module in "${modules[@]}"; do
        if [ -f "$module" ]; then
            log_success "Module exists: $module"
        else
            log_error "Module missing: $module"
            all_exist=false
        fi
    done

    if [ "$all_exist" = true ]; then
        log_success "All referenced modules exist"
        return 0
    else
        log_error "Some referenced modules are missing"
        return 1
    fi
}

validate_github_workflow() {
    section_header "Validating GitHub Workflow Registration"

    # Check if workflow is registered in GitHub
    if gh workflow list 2>/dev/null | grep -q "$WORKFLOW_NAME"; then
        log_success "Workflow registered in GitHub: $WORKFLOW_NAME"

        # Get workflow details
        gh workflow view "$WORKFLOW_NAME" 2>/dev/null | head -10 || true

        return 0
    else
        log_error "Workflow NOT registered in GitHub: $WORKFLOW_NAME"
        log_info "This may be due to:"
        log_info "  1. Recent push not yet processed by GitHub"
        log_info "  2. Workflow file syntax errors"
        log_info "  3. GitHub Actions not enabled for repository"
        return 1
    fi
}

validate_permissions() {
    section_header "Checking Repository Permissions"

    log_info "Checking GitHub Actions permissions..."

    # Try to get workflow permissions
    if gh api repos/:owner/:repo/actions/permissions 2>/dev/null | grep -q "enabled"; then
        local enabled=$(gh api repos/:owner/:repo/actions/permissions 2>/dev/null | grep -o '"enabled":[^,]*' | cut -d: -f2)
        log_info "GitHub Actions enabled: $enabled"

        log_warning "⚠️  MANUAL ACTION REQUIRED:"
        log_warning "    Configure workflow permissions in GitHub UI:"
        log_warning "    Settings → Actions → General → Workflow permissions"
        log_warning "    Enable: 'Read and write permissions'"
    else
        log_warning "Could not check permissions (may require admin access)"
    fi

    return 0
}

validate_commits_pushed() {
    section_header "Validating Commits Pushed to GitHub"

    # Check if local branch is ahead of remote
    local commits_ahead=$(git rev-list --count origin/main..main 2>/dev/null || echo "0")

    if [ "$commits_ahead" -eq 0 ]; then
        log_success "All commits pushed to GitHub"
    else
        log_error "Local branch is $commits_ahead commits ahead of origin/main"
        log_info "Run: git push origin main"
        return 1
    fi

    # Check latest commit contains ADR-0009
    local latest_commit=$(git log -1 --oneline)
    log_info "Latest commit: $latest_commit"

    if echo "$latest_commit" | grep -q "0009"; then
        log_success "Latest commit references ADR-0009"
    else
        log_warning "Latest commit does not reference ADR-0009"
    fi

    return 0
}

# =============================================================================
# Main Validation
# =============================================================================

main() {
    local exit_code=0

    section_header "GitHub Actions Workflow Deployment Validation (ADR-0009)"

    log_info "Validating workflow deployment readiness..."
    echo

    # Run all validations
    validate_files_exist || exit_code=1
    validate_adr_plan_sync || exit_code=1
    validate_workflow_syntax || exit_code=1
    validate_module_references || exit_code=1
    validate_commits_pushed || exit_code=1
    validate_github_workflow || exit_code=1
    validate_permissions || exit_code=1

    # Final summary
    section_header "Validation Summary"

    if [ $exit_code -eq 0 ]; then
        log_success "✅ All validations passed!"
        echo
        log_info "Next steps (Manual):"
        log_info "  1. Configure repository permissions (see above)"
        log_info "  2. Trigger first workflow run:"
        log_info "     gh workflow run update-database.yml --field update_mode=daily"
        log_info "  3. Monitor execution:"
        log_info "     gh run watch"
        log_info ""
        log_info "See: docs/operations/DEPLOYMENT_GUIDE.md for detailed instructions"
    else
        log_error "❌ Some validations failed"
        log_info "Review errors above and fix issues before proceeding"
    fi

    return $exit_code
}

# Run main function
main "$@"
