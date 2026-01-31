#!/bin/bash
#
# Setup script for nginx and SSL on feedyourresearch.online
# Run with sudo: sudo bash scripts/setup-nginx-ssl.sh
#

set -e

# Configuration
DOMAIN="feedyourresearch.online"
APP_PORT=8000
APP_USER="www-data"
APP_DIR="/var/www/feedresearch"
EMAIL="${CERTBOT_EMAIL:-admin@$DOMAIN}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (sudo bash $0)"
    exit 1
fi

# =============================================================================
# Step 1: Install nginx and certbot
# =============================================================================
log_info "Installing nginx and certbot..."

apt-get update
apt-get install -y nginx certbot python3-certbot-nginx

log_info "nginx and certbot installed"

# =============================================================================
# Step 2: Create initial HTTP-only nginx configuration (for certbot)
# =============================================================================
log_info "Creating initial HTTP-only nginx configuration..."

cat > /etc/nginx/sites-available/$DOMAIN << 'NGINX_HTTP_CONFIG'
# Temporary HTTP-only config for certbot
server {
    listen 80;
    listen [::]:80;
    server_name feedyourresearch.online www.feedyourresearch.online;

    # Allow ACME challenge for certificate
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Proxy to app for now
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX_HTTP_CONFIG

# Create rate limiting zone in nginx.conf if not exists
if ! grep -q "limit_req_zone.*admin_limit" /etc/nginx/nginx.conf; then
    log_info "Adding rate limiting zone to nginx.conf..."
    sed -i '/http {/a \    # Rate limiting for admin API\n    limit_req_zone $binary_remote_addr zone=admin_limit:10m rate=5r/s;' /etc/nginx/nginx.conf
fi

# Enable site
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/

log_info "Initial nginx configuration created"

# =============================================================================
# Step 3: Test and reload nginx
# =============================================================================
log_info "Testing nginx configuration..."

nginx -t

log_info "Reloading nginx..."
systemctl reload nginx

# =============================================================================
# Step 4: Obtain SSL certificate
# =============================================================================
log_info "Obtaining SSL certificate..."

# Check if certificate already exists
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    log_warn "Certificate already exists, skipping certbot"
else
    certbot certonly --webroot \
        -w /var/www/html \
        -d $DOMAIN \
        -d www.$DOMAIN \
        --non-interactive \
        --agree-tos \
        --email $EMAIL
fi

log_info "SSL certificate obtained"

# =============================================================================
# Step 5: Create full HTTPS nginx configuration
# =============================================================================
log_info "Creating full HTTPS nginx configuration..."

cat > /etc/nginx/sites-available/$DOMAIN << 'NGINX_CONFIG'
# HTTP redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name feedyourresearch.online www.feedyourresearch.online;

    # Allow ACME challenge for certificate renewal
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name feedyourresearch.online www.feedyourresearch.online;

    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/feedyourresearch.online/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/feedyourresearch.online/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Logging
    access_log /var/log/nginx/feedyourresearch.online.access.log;
    error_log /var/log/nginx/feedyourresearch.online.error.log;

    # Static files with caching
    location /static/ {
        alias /var/www/feedresearch/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";

        # Gzip compression
        gzip on;
        gzip_types text/css application/javascript application/json;
    }

    # Rate limiting for admin endpoints
    location /admin/api/ {
        limit_req zone=admin_limit burst=10 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket/SSE support for streaming endpoints
    location /research {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # SSE specific settings
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # Main application proxy
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
NGINX_CONFIG

# Test and reload
nginx -t
systemctl reload nginx

log_info "HTTPS configuration applied"

# =============================================================================
# Step 6: Create systemd service for the application
# =============================================================================
log_info "Creating systemd service..."

cat > /etc/systemd/system/feedresearch.service << 'SERVICE_CONFIG'
[Unit]
Description=Feed Your Research - Multi-Agent Research System
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/feedresearch
Environment="PATH=/var/www/feedresearch/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/var/www/feedresearch/venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/www/feedresearch/data
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICE_CONFIG

systemctl daemon-reload

log_info "systemd service created"

# =============================================================================
# Step 7: Set proper file permissions
# =============================================================================
log_info "Setting file permissions..."

# Create data directory if not exists
mkdir -p $APP_DIR/data

# Set ownership
chown -R $APP_USER:$APP_USER $APP_DIR

# Set directory permissions
find $APP_DIR -type d -exec chmod 755 {} \;

# Set file permissions
find $APP_DIR -type f -exec chmod 644 {} \;

# Make scripts executable
chmod +x $APP_DIR/scripts/*.sh 2>/dev/null || true

# Ensure venv binaries are executable
if [ -d "$APP_DIR/venv" ]; then
    chmod +x $APP_DIR/venv/bin/*
fi

log_info "Permissions set"

# =============================================================================
# Step 8: Enable auto-renewal for certificates
# =============================================================================
log_info "Setting up certificate auto-renewal..."

# Test renewal
certbot renew --dry-run

# Create renewal hook to reload nginx
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh << 'HOOK'
#!/bin/bash
systemctl reload nginx
HOOK
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

log_info "Auto-renewal configured"

# =============================================================================
# Step 9: Start services
# =============================================================================
log_info "Starting services..."

systemctl enable nginx
systemctl enable feedresearch
systemctl start nginx
systemctl restart feedresearch || log_warn "feedresearch service failed to start (may need venv setup)"

log_info "Services started"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=============================================="
echo ""
echo "Your site should now be available at:"
echo "  https://$DOMAIN"
echo "  https://$DOMAIN/admin (Admin Panel)"
echo "  https://$DOMAIN/ui (Research UI)"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status feedresearch  # Check app status"
echo "  sudo systemctl restart feedresearch # Restart app"
echo "  sudo systemctl status nginx         # Check nginx status"
echo "  sudo journalctl -u feedresearch -f  # View app logs"
echo "  sudo certbot renew --dry-run        # Test cert renewal"
echo ""
echo "Admin panel default password: admin"
echo -e "${YELLOW}Please change it immediately after first login!${NC}"
echo ""
