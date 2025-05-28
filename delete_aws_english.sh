#!/bin/bash
# Simple script to delete WhisperX AWS resources

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

log "Deleting AWS resources for WhisperX in region $REGION"

# 1. Terminate EC2 instance(s)
log "Looking for EC2 instance(s) with name '$INSTANCE_NAME'..."

INSTANCE_IDS=$(aws ec2 describe-instances --region $REGION \
    --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running,stopped,pending,stopping" \
    --query "Reservations[*].Instances[*].InstanceId" \
    --output text)

if [[ -z "$INSTANCE_IDS" || "$INSTANCE_IDS" == "None" ]]; then
    warn "No EC2 instance(s) with name '$INSTANCE_NAME' found."
else
    log "Found EC2 instance(s): $INSTANCE_IDS"
    log "Terminating EC2 instance(s)..."
    
    aws ec2 terminate-instances --region $REGION --instance-ids $INSTANCE_IDS > /dev/null
    
    if [[ $? -ne 0 ]]; then
        error "Error terminating EC2 instance(s)."
    else
        log "EC2 instance(s) are being terminated. This may take a few minutes."
        log "Waiting for instance(s) to terminate..."
        aws ec2 wait instance-terminated --region $REGION --instance-ids $INSTANCE_IDS
        log "EC2 instance(s) successfully terminated."
    fi
fi

# 2. Delete security group
log "Looking for security group 'whisperx-sg'..."

SG_ID=$(aws ec2 describe-security-groups --region $REGION \
    --filters "Name=group-name,Values=whisperx-sg" \
    --query "SecurityGroups[0].GroupId" \
    --output text)

if [[ -z "$SG_ID" || "$SG_ID" == "None" ]]; then
    warn "No security group 'whisperx-sg' found."
else
    log "Found security group: $SG_ID"
    log "Deleting security group..."
    
    # Wait a bit as the security group might still be attached to the instance
    sleep 5
    
    aws ec2 delete-security-group --region $REGION --group-id $SG_ID
    
    if [[ $? -ne 0 ]]; then
        warn "Error deleting security group. It might still be attached to resources."
        warn "Try again later or delete it manually in the AWS console."
    else
        log "Security group successfully deleted."
    fi
fi

# 3. Delete key pair
log "Looking for key pair 'whisperx-key'..."

KEY_EXISTS=$(aws ec2 describe-key-pairs --region $REGION \
    --key-names whisperx-key \
    --query "KeyPairs[0].KeyName" \
    --output text 2>/dev/null)

if [[ -z "$KEY_EXISTS" || "$KEY_EXISTS" == "None" ]]; then
    warn "No key pair 'whisperx-key' found."
else
    log "Found key pair: $KEY_EXISTS"
    log "Deleting key pair..."
    
    aws ec2 delete-key-pair --region $REGION --key-name whisperx-key
    
    if [[ $? -ne 0 ]]; then
        error "Error deleting key pair."
    else
        log "Key pair successfully deleted."
        
        # Delete local key file
        if [[ -f "whisperx-key.pem" ]]; then
            log "Deleting local key file 'whisperx-key.pem'..."
            rm whisperx-key.pem
            log "Local key file successfully deleted."
        fi
    fi
fi

log "Cleanup completed."