#!/bin/bash
# EC2 User Data script - runs on instance startup

set -e

# Update system
yum update -y

# Install Docker
yum install -y docker
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install AWS CLI v2 (if not already installed)
if ! command -v aws &> /dev/null; then
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    ./aws/install
    rm -rf aws awscliv2.zip
fi

# Create application directory
mkdir -p /opt/jobsys
cd /opt/jobsys

# Note: Application files should be copied here via:
# - S3 bucket with application files
# - Git clone
# - Or use AWS CodeDeploy/Systems Manager

# Create docker-compose file (will be created by deployment script)
# The deployment script will create docker-compose.prod.yml here

# Set up log rotation for Docker
cat > /etc/logrotate.d/docker-containers <<EOF
/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    size=1M
    missingok
    delaycompress
    copytruncate
}
EOF

# Create systemd service for docker-compose (optional - for auto-restart)
cat > /etc/systemd/system/jobsys.service <<'SERVICE_EOF'
[Unit]
Description=Job System Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/jobsys
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Enable the service (but don't start yet - wait for files to be deployed)
systemctl daemon-reload
# systemctl enable jobsys.service

echo "✅ EC2 initialization complete!"
echo "Waiting for application deployment..."

