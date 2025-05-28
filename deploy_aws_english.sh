#!/bin/bash
# Simple script to deploy WhisperX on AWS with GPU support

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
GPU_TYPE="t4"

# Parse parameters
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -r|--region) REGION="$2"; shift ;;
        -t|--type) GPU_TYPE="$2"; shift ;;
        *) shift ;;
    esac
    shift
done

# Set instance type based on GPU type
if [[ "$GPU_TYPE" == "t4" ]]; then
    INSTANCE_TYPE="g4dn.xlarge"
    log "GPU Type: T4 (g4dn.xlarge)"
elif [[ "$GPU_TYPE" == "a10g" ]]; then
    INSTANCE_TYPE="g5.xlarge"
    log "GPU Type: A10G (g5.xlarge)"
else
    error "Unknown GPU type: $GPU_TYPE. Supported types: t4, a10g"
    exit 1
fi

log "Starting EC2 instance in region: $REGION, instance type: $INSTANCE_TYPE"

# 1. Create key pair if it doesn't exist
log "Checking for key pair..."
if aws ec2 describe-key-pairs --region $REGION --key-names whisperx-key &> /dev/null; then
    log "Key pair 'whisperx-key' already exists."
else
    log "Creating new key pair 'whisperx-key'..."
    aws ec2 create-key-pair --region $REGION --key-name whisperx-key --query 'KeyMaterial' --output text > whisperx-key.pem
    chmod 400 whisperx-key.pem
    log "Key pair created and saved to 'whisperx-key.pem'."
fi

# 2. Create security group if it doesn't exist
log "Checking for security group..."
SG_ID=$(aws ec2 describe-security-groups --region $REGION --filters "Name=group-name,Values=whisperx-sg" --query "SecurityGroups[0].GroupId" --output text 2>/dev/null)

if [[ "$SG_ID" != "None" && "$SG_ID" != "" ]]; then
    log "Security group 'whisperx-sg' already exists with ID: $SG_ID"
else
    log "Creating new security group 'whisperx-sg'..."
    SG_ID=$(aws ec2 create-security-group --region $REGION \
        --group-name whisperx-sg \
        --description "Security Group for WhisperX Server" \
        --query "GroupId" --output text)
    
    log "Adding security rules..."
    # Allow SSH
    aws ec2 authorize-security-group-ingress --region $REGION \
        --group-id $SG_ID \
        --protocol tcp \
        --port 22 \
        --cidr 0.0.0.0/0 > /dev/null
    
    # Allow WhisperX API on port 8000
    aws ec2 authorize-security-group-ingress --region $REGION \
        --group-id $SG_ID \
        --protocol tcp \
        --port 8000 \
        --cidr 0.0.0.0/0 > /dev/null
    
    log "Security group created with ID: $SG_ID"
fi

# 3. Find latest Ubuntu AMI
log "Finding latest Ubuntu AMI..."
AMI_ID=$(aws ec2 describe-images --region $REGION \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    "Name=state,Values=available" \
    --query "sort_by(Images, &CreationDate)[-1].ImageId" \
    --output text)

log "Using AMI: $AMI_ID"

# 4. Create user data script
log "Creating user data script..."
USER_DATA=$(cat <<'EOF'
#!/bin/bash
exec > >(tee /var/log/user-data.log) 2>&1
echo "Starting WhisperX installation..."

# System updates
apt-get update && apt-get upgrade -y

# Install basic tools
apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release git jq

# Install Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker ubuntu

# Install NVIDIA driver and container runtime
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | tee /etc/apt/sources.list.d/nvidia-docker.list
apt-get update
apt-get install -y nvidia-docker2
systemctl restart docker

# Clone repository
cd /home/ubuntu
git clone https://github.com/pavelzbornik/whisperX-FastAPI-cuda.git
chown -R ubuntu:ubuntu whisperX-FastAPI-cuda

# Create environment file
cat > /home/ubuntu/whisperX-FastAPI-cuda/.env <<ENVFILE
# WhisperX Configuration
HF_TOKEN=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
WHISPER_MODEL=base
DEFAULT_LANG=en
DEVICE=cuda
COMPUTE_TYPE=float16
LOG_LEVEL=INFO
ENVIRONMENT=production
ENVFILE

# Create directories for persistent data
mkdir -p /data/whisperx/cache /data/whisperx/tmp
chmod -R 777 /data/whisperx

# Start Docker container
cd /home/ubuntu/whisperX-FastAPI-cuda
docker compose up -d

# Check NVIDIA status
echo "NVIDIA Status:"
nvidia-smi

echo "WhisperX installation completed."
echo "API should be available at http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"
EOF
)

# 5. Launch the EC2 instance
log "Creating EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances --region $REGION \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --key-name whisperx-key \
    --security-group-ids $SG_ID \
    --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":50,\"VolumeType\":\"gp3\"}}]" \
    --user-data "$USER_DATA" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --query "Instances[0].InstanceId" \
    --output text)

if [[ $? -ne 0 || -z "$INSTANCE_ID" ]]; then
    error "Failed to create EC2 instance."
    exit 1
fi

log "EC2 instance being created with ID: $INSTANCE_ID"
log "Waiting for instance to start..."

# 6. Wait for the instance to be running
aws ec2 wait instance-running --region $REGION --instance-ids $INSTANCE_ID

# 7. Get the public IP address
PUBLIC_IP=$(aws ec2 describe-instances --region $REGION \
    --instance-ids $INSTANCE_ID \
    --query "Reservations[0].Instances[0].PublicIpAddress" \
    --output text)

log "EC2 instance successfully created!"
log "Instance ID: $INSTANCE_ID"
log "Public IP: $PUBLIC_IP"
log "SSH access: ssh -i whisperx-key.pem ubuntu@$PUBLIC_IP"
log "WhisperX API will be available at http://$PUBLIC_IP:8000"
log "Installation is running in the background and may take several minutes."
log "To check progress, connect via SSH and run:"
log "  tail -f /var/log/user-data.log"