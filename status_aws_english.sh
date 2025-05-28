#!/bin/bash
# Simple script to check status of WhisperX EC2 instance

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Log functions
log() { echo -e "${GREEN}[INFO] $1${NC}"; }
warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
info() { echo -e "${BLUE}[INFO] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; }

# Default values
REGION="eu-central-1"
INSTANCE_NAME="whisperx-server"

# Parse parameters
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -r|--region) REGION="$2"; shift ;;
        -n|--name) INSTANCE_NAME="$2"; shift ;;
        *) shift ;;
    esac
    shift
done

log "Checking status of EC2 instance with name '$INSTANCE_NAME' in region '$REGION'..."

# Get instance details
INSTANCE_DETAILS=$(aws ec2 describe-instances --region $REGION \
    --filters "Name=tag:Name,Values=$INSTANCE_NAME" \
    --query "Reservations[0].Instances[0].{InstanceId:InstanceId,State:State.Name,PublicIP:PublicIpAddress,InstanceType:InstanceType,LaunchTime:LaunchTime}" \
    --output json)

if [[ -z "$INSTANCE_DETAILS" || "$INSTANCE_DETAILS" == "null" ]]; then
    warn "No EC2 instance with name '$INSTANCE_NAME' found."
    exit 1
fi

# Parse JSON response
INSTANCE_ID=$(echo $INSTANCE_DETAILS | jq -r '.InstanceId')
STATE=$(echo $INSTANCE_DETAILS | jq -r '.State')
PUBLIC_IP=$(echo $INSTANCE_DETAILS | jq -r '.PublicIP')
INSTANCE_TYPE=$(echo $INSTANCE_DETAILS | jq -r '.InstanceType')
LAUNCH_TIME=$(echo $INSTANCE_DETAILS | jq -r '.LaunchTime')

if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "null" ]]; then
    warn "No EC2 instance with name '$INSTANCE_NAME' found."
    exit 1
fi

log "EC2 instance found!"
log "Instance ID: $INSTANCE_ID"
log "Status: $STATE"
log "Public IP: $PUBLIC_IP"
log "Instance Type: $INSTANCE_TYPE"
log "Launch Time: $LAUNCH_TIME"

if [[ "$STATE" == "running" && -n "$PUBLIC_IP" ]]; then
    log "SSH access: ssh -i whisperx-key.pem ubuntu@$PUBLIC_IP"
    log "WhisperX API URL: http://$PUBLIC_IP:8000"
    log "WhisperX API Documentation: http://$PUBLIC_IP:8000/docs"
    
    # Check if API is reachable
    if curl -s -o /dev/null -w "%{http_code}" http://$PUBLIC_IP:8000/health 2>/dev/null | grep -q "200"; then
        log "✅ WhisperX API is up and running!"
    else
        warn "⚠️  WhisperX API does not appear to be ready yet."
        log "You can check installation progress by connecting via SSH:"
        log "  ssh -i whisperx-key.pem ubuntu@$PUBLIC_IP"
        log "  sudo tail -f /var/log/user-data.log"
    fi
fi