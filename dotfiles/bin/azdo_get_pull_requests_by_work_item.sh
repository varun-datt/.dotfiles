#!/usr/bin/env bash

set -e

# Configuration variables
ORG=""
PROJECT=""
MAX_DEPTH=100
INITIAL_WORK_ITEM_ID=""
OUTPUT_FILE="work_item_prs.csv"
LOG_FILE="get_work_item_prs.log"
SLEEP_TIME=1  # Base sleep time for exponential backoff

# ANSI color codes for prettier output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" | tee -a "$LOG_FILE"
}

info() {
    echo "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1${NC}" | tee -a "$LOG_FILE"
}

success() {
    echo "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}" | tee -a "$LOG_FILE"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    # Check if az CLI is installed
    if ! command -v az &> /dev/null; then
        error "Azure CLI is not installed. Please install it first."
        echo "Visit https://docs.microsoft.com/en-us/cli/azure/install-azure-cli for installation instructions"
        exit 1
    fi

    # Check if logged in
    if ! az account show &> /dev/null; then
        error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    fi

    # Check if the Azure DevOps extension is installed
    if ! az extension list | grep -q "azure-devops"; then
        warning "Azure DevOps extension not found. Installing..."
        az extension add --name azure-devops
    fi

    success "Prerequisites check completed."
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --org)
                ORG="$2"
                shift 2
                ;;
            --project)
                PROJECT="$2"
                shift 2
                ;;
            --work-item)
                INITIAL_WORK_ITEM_ID="$2"
                shift 2
                ;;
            --max-depth)
                MAX_DEPTH="$2"
                shift 2
                ;;
            --output)
                OUTPUT_FILE="$2"
                shift 2
                ;;
            *)
                error "Unknown parameter: $1"
                echo "Usage: $0 --org <organization> --project <project> --work-item <id> [--max-depth <number>] [--output <filename>]"
                exit 1
                ;;
        esac
    done

    # Validate required parameters
    if [[ -z "$ORG" ]]; then
        error "Organization (--org) is required"
        exit 1
    fi

    if [[ -z "$PROJECT" ]]; then
        error "Project (--project) is required"
        exit 1
    fi

    if [[ -z "$INITIAL_WORK_ITEM_ID" ]]; then
        error "Initial work item ID (--work-item) is required"
        exit 1
    fi
}

# Configure Azure DevOps CLI
configure_azure_devops() {
    info "Configuring Azure DevOps CLI..."

    # Configure the Azure DevOps organization
    az devops configure --defaults organization="$ORG" project="$PROJECT"

    success "Azure DevOps CLI configured with organization: $ORG, project: $PROJECT"
}

# Function to extract PR links from a work item
get_pr_links_for_work_item() {
    local work_item_id="$1"
    local depth="$2"
    local indent=$(printf '%*s' "$((depth * 2))" '')

    # Skip if we've reached max depth
    if [[ $depth -gt $MAX_DEPTH ]]; then
        warning "${indent}Reached maximum recursion depth ($MAX_DEPTH)"
        return 0
    fi

    info "${indent}Processing work item #$work_item_id (Depth: $depth/$MAX_DEPTH)"

    # Get work item details including relationships
    # Use awk to extract everything from the first { to the end (handles multi-line JSON)
    work_item_details=$(az boards work-item show --id $work_item_id --output json | awk 'BEGIN{flag=0; result=""} /\{/{flag=1} flag{result=result $0 ORS} END{print result}' | jq)

    if [[ -z "$work_item_details" ]]; then
        error "${indent}Failed to get details for work item #$work_item_id"
        return 1
    fi

    # Extract work item title and type using the JSON file
    local work_item_title=$(printf '%s' "$work_item_details" | jq -r '.fields."System.Title"')
    local work_item_type=$(printf '%s' "$work_item_details" | jq -r '.fields."System.WorkItemType"')
    local work_item_state=$(printf '%s' "$work_item_details" | jq -r '.fields."System.State"')

    info "${indent}Work Item: #$work_item_id - $work_item_type - $work_item_state - \"$work_item_title\""

    # Get pull request links from work item
    local pr_links
    pr_links=$(printf '%s' "$work_item_details" | jq -r '.relations[] | select(.attributes.name == "Pull Request") | .url')

    # If we have PR links, print them and add to output file
    if [[ -n "$pr_links" ]]; then
        echo "$pr_links" | while read -r pr_link; do
            local ids_part=$(echo "$pr_link" | cut -d'/' -f6)

            # Split by %2F (URL-encoded slash)
            arr=($(echo "$ids_part" | sed 's/%2F/ /g'))
            len=${#arr[@]}
            local pr_id="${arr[$((len-1))]}"
            local repo_id="${arr[$((len-2))]}"

            # Construct the Azure DevOps UI URL using the organization and project name
            # Note: We need to use org name and project name instead of GUIDs for the URL
            local pr_ui_url="$ORG/$PROJECT/_git/$repo_id/pullrequest/$pr_id"

            success "${indent}- Pull Request #$pr_id: $pr_ui_url"

            # Add to output CSV file
            echo "$work_item_id,$work_item_type,\"$work_item_title\",$pr_id,$pr_ui_url" >> "$OUTPUT_FILE"

            # Try to get PR details
            local pr_details
            # Use the same approach for PR details
            pr_details=$(az repos pr show --id $pr_id --output json 2>/dev/null | awk 'BEGIN{flag=0; result=""} /\{/{flag=1} flag{result=result $0 ORS} END{print result}' | jq)

            # Clean the PR JSON too
            if [[ -n "$pr_details" ]]; then
                local pr_status=$(printf '%s' "$pr_details" | jq -r '.status')
                local pr_title=$(printf '%s' "$pr_details" | jq -r '.title')
                local pr_created_by=$(printf '%s' "$pr_details" | jq -r '.createdBy.displayName')

                info "${indent}  PR Status: $pr_status, Title: \"$pr_title\", Created by: $pr_created_by"
            fi
        done
    else
        warning "${indent}No Pull Request links found for work item #$work_item_id"
    fi

    # Get child work items and recursively process them
    local related_work_items
    related_work_items=$(printf '%s' "$work_item_details" | jq -r '.relations[] | select(.attributes.name == "Child") | .url')

    if [[ -n "$related_work_items" ]]; then
        info "${indent}Found related work items for #$work_item_id"

        printf '%s\n' "$related_work_items" | while read -r related_url; do
            # Extract work item ID from URL
            local related_id=$(echo "$related_url" | awk -F/ '{print $NF}')
            info "${indent}Processing related work item: #$related_id"

            # Recursively get PR links for related work item
            get_pr_links_for_work_item "$related_id" $((depth + 1))
        done
    else
        info "${indent}No child or related work items found for #$work_item_id"
    fi
}

main() {
    log "Starting script to extract pull request links from work items"

    check_prerequisites
    parse_args "$@"
    configure_azure_devops

    # Create/reset output file with header
    echo "WorkItemID,WorkItemType,WorkItemTitle,PullRequestID,PullRequestURL" > "$OUTPUT_FILE"

    # Start processing from initial work item
    get_pr_links_for_work_item "$INITIAL_WORK_ITEM_ID" 1

    success "Script completed successfully. Results saved to $OUTPUT_FILE"
}

# Execute main function with all script arguments
main "$@"

