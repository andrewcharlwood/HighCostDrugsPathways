# Reflex Deployment Guide

This guide covers deployment options for the Patient Pathway Analysis web application built with Reflex.

## Overview

Reflex applications compile to a FastAPI backend and Next.js frontend. This creates two deployment artifacts that can be deployed together or separately depending on your infrastructure requirements.

## Development Mode

For local development:

```bash
# Start development server with hot reload
reflex run

# Access the application at http://localhost:3000
```

## Production Deployment Options

### Option 1: Simple Production (Single Server)

The simplest approach for internal deployments:

```bash
# Run in production mode (optimized build)
reflex run --env prod
```

This starts:
- FastAPI backend on port 8000
- Next.js frontend on port 3000

For background execution:

```bash
# Using nohup (Linux/macOS)
nohup reflex run --env prod > reflex.log 2>&1 &

# Using PowerShell (Windows)
Start-Process -NoNewWindow -FilePath "reflex" -ArgumentList "run --env prod"
```

### Option 2: Separate Backend and Frontend

For more control, run backend and frontend separately:

```bash
# Terminal 1: Start backend only
reflex run --env prod --backend-only

# Terminal 2: Start frontend only
reflex run --env prod --frontend-only
```

### Option 3: Static Export

Export the frontend as static files for deployment on static hosting or CDN:

```bash
# Export application
reflex export

# This creates:
# - frontend.zip (static Next.js build)
# - backend.zip (Python application source)
```

Then:
1. Unzip `frontend.zip` and serve via nginx, Apache, or any static file server
2. Run the backend separately using uvicorn/gunicorn

### Option 4: Docker Deployment

Create a `Dockerfile` for containerized deployment:

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Node.js for Reflex frontend build
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Initialize Reflex (downloads frontend dependencies)
RUN reflex init --loglevel debug

# Expose ports
EXPOSE 3000 8000

# Start in production mode
CMD ["reflex", "run", "--env", "prod"]
```

Build and run:

```bash
# Build the image
docker build -t pathway-analysis .

# Run the container
docker run -p 3000:3000 -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  pathway-analysis
```

### Option 5: Docker Compose (Recommended for Production)

Create `docker-compose.yml` for multi-container deployment:

```yaml
version: '3.8'

services:
  backend:
    build: .
    command: reflex run --env prod --backend-only
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - REFLEX_ENV=prod
    restart: unless-stopped

  frontend:
    build: .
    command: reflex run --env prod --frontend-only
    ports:
      - "3000:3000"
    depends_on:
      - backend
    environment:
      - REFLEX_ENV=prod
    restart: unless-stopped
```

Run with:

```bash
docker-compose up -d
```

## Reverse Proxy Configuration

### Nginx

For production deployments behind nginx:

```nginx
# /etc/nginx/sites-available/pathway-analysis
server {
    listen 80;
    server_name your-server.nhs.uk;

    # Backend API endpoints
    location /admin {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ping {
        proxy_pass http://localhost:8000;
    }

    location /upload {
        proxy_pass http://localhost:8000;
        client_max_body_size 100M;  # For large data file uploads
    }

    # WebSocket connections (required for Reflex state sync)
    location /_event/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;  # 24 hours for long-running connections
    }

    # Frontend (all other requests)
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/pathway-analysis /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Caddy (Alternative)

Caddy provides automatic HTTPS:

```caddyfile
# Caddyfile
your-server.nhs.uk {
    # Backend API
    handle /admin/* {
        reverse_proxy localhost:8000
    }
    handle /ping {
        reverse_proxy localhost:8000
    }
    handle /upload {
        reverse_proxy localhost:8000
    }
    handle /_event/* {
        reverse_proxy localhost:8000
    }

    # Frontend
    handle {
        reverse_proxy localhost:3000
    }
}
```

## Process Management

### Systemd (Linux)

Create service files for automatic startup:

```ini
# /etc/systemd/system/pathway-backend.service
[Unit]
Description=Pathway Analysis Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/pathway-analysis
ExecStart=/usr/bin/reflex run --env prod --backend-only
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/pathway-frontend.service
[Unit]
Description=Pathway Analysis Frontend
After=network.target pathway-backend.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/pathway-analysis
ExecStart=/usr/bin/reflex run --env prod --frontend-only
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pathway-backend pathway-frontend
sudo systemctl start pathway-backend pathway-frontend
```

### Windows Service

Use NSSM (Non-Sucking Service Manager) on Windows:

```powershell
# Install NSSM
choco install nssm

# Create service
nssm install PathwayAnalysis "C:\Path\To\reflex.exe" "run --env prod"
nssm set PathwayAnalysis AppDirectory "C:\Path\To\Patient pathway analysis"
nssm start PathwayAnalysis
```

## Environment Configuration

### Production Environment Variables

Set these environment variables for production:

```bash
# Reflex configuration
export REFLEX_ENV=prod

# Database paths (if using custom locations)
export PATHWAY_DB_PATH=/var/data/pathways.db
export PATHWAY_CACHE_DIR=/var/cache/pathway-analysis

# Snowflake (if using)
export SNOWFLAKE_ACCOUNT=your-account
export SNOWFLAKE_WAREHOUSE=your-warehouse
```

### Snowflake Configuration

Ensure `config/snowflake.toml` is properly configured for production:

```toml
[connection]
account = "your-production-account"
warehouse = "ANALYTICS_WH"
database = "DATA_HUB"
schema = "CDM"
authenticator = "externalbrowser"  # or "oauth" for service accounts

[cache]
enabled = true
directory = "/var/cache/pathway-analysis"
ttl_seconds = 86400  # 24 hours
```

## Reflex Cloud

For managed hosting, consider [Reflex Cloud](https://reflex.dev/cloud/):

```bash
# Deploy to Reflex Cloud
reflex deploy
```

Benefits:
- Zero configuration deployment
- Automatic scaling
- Built-in SSL certificates
- Managed state management with Redis

## Security Considerations

### Network Security

1. **Firewall Rules**: Only expose necessary ports (typically just 80/443)
2. **HTTPS**: Use TLS certificates (Let's Encrypt or organizational certs)
3. **VPN**: Consider restricting access to NHS network only

### Data Security

1. **Database Access**: Ensure SQLite database permissions are restricted
2. **File Uploads**: Validate file types and scan for malware
3. **Snowflake**: Use least-privilege service accounts

### Authentication

For NHS deployments, consider adding authentication:

```python
# Example: Add basic auth middleware
import reflex as rx
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware

# In rxconfig.py
config = rx.Config(
    app_name="pathways_app",
    # Add authentication middleware
)
```

## Monitoring

### Health Checks

The application provides endpoints for monitoring:

- `/ping` - Basic health check
- Backend port 8000 - FastAPI health

### Logging

Configure logging for production:

```python
# In pathways_app/pathways_app.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/pathway-analysis/app.log'),
        logging.StreamHandler()
    ]
)
```

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Find and kill process using port 3000
lsof -i :3000
kill -9 <PID>
```

**Build cache issues:**
```bash
# Clear Reflex build cache
rm -rf .web
reflex run --env prod
```

**Database connection errors:**
```bash
# Verify database exists and has correct permissions
ls -la data/pathways.db
sqlite3 data/pathways.db ".tables"
```

**Snowflake authentication:**
- Ensure browser is available for SSO popup
- Check firewall allows connections to Snowflake endpoints
- Verify account identifier is correct

## Performance Tuning

### Backend (FastAPI/Uvicorn)

For high-traffic deployments:

```bash
# Run with multiple workers
uvicorn pathways_app:app --workers 4 --host 0.0.0.0 --port 8000
```

### State Management

For multi-instance deployments, configure Redis for state management:

```python
# rxconfig.py
config = rx.Config(
    app_name="pathways_app",
    state_manager_mode="redis",
    redis_url="redis://localhost:6379/0",
)
```

### Caching

Enable aggressive caching for Snowflake queries in `config/snowflake.toml`:

```toml
[cache]
enabled = true
ttl_seconds = 86400  # 24 hours for historical data
ttl_current_data_seconds = 3600  # 1 hour for recent data
max_size_mb = 1000  # 1GB cache
```

---

## Quick Reference

| Environment | Command | Ports |
|-------------|---------|-------|
| Development | `reflex run` | 3000, 8000 |
| Production | `reflex run --env prod` | 3000, 8000 |
| Backend only | `reflex run --backend-only` | 8000 |
| Frontend only | `reflex run --frontend-only` | 3000 |
| Export | `reflex export` | Static files |
| Cloud | `reflex deploy` | Managed |

For more information, see:
- [Reflex Documentation](https://reflex.dev/docs/)
- [Reflex Cloud](https://reflex.dev/cloud/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
