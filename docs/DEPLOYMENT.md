# Deployment Guide

This guide covers deployment options for the Patient Pathway Analysis web application built with Dash.

## Overview

The application is a single-process Python Dash app that serves both the frontend and API from one server. It reads pre-computed data from a local SQLite database.

## Development Mode

For local development:

```bash
# Start development server with hot reload
python run_dash.py

# Access the application at http://localhost:8050
```

## Production Deployment Options

### Option 1: Simple Production (Single Server)

The simplest approach for internal deployments:

```bash
# Run with Gunicorn (Linux/macOS)
gunicorn dash_app.app:server -b 0.0.0.0:8050 --workers 4

# Or directly with Python
python run_dash.py
```

For background execution:

```bash
# Using nohup (Linux/macOS)
nohup gunicorn dash_app.app:server -b 0.0.0.0:8050 --workers 4 > dash.log 2>&1 &

# Using PowerShell (Windows)
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "run_dash.py"
```

### Option 2: Docker Deployment

Create a `Dockerfile` for containerized deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev

# Copy application code
COPY src/ src/
COPY dash_app/ dash_app/
COPY data/ data/
COPY run_dash.py setup_dev.py ./

# Set up Python path
RUN uv run python setup_dev.py

# Expose port
EXPOSE 8050

# Start the application
CMD ["uv", "run", "gunicorn", "dash_app.app:server", "-b", "0.0.0.0:8050", "--workers", "4"]
```

Build and run:

```bash
# Build the image
docker build -t pathway-analysis .

# Run the container
docker run -p 8050:8050 \
  -v $(pwd)/data:/app/data \
  pathway-analysis
```

### Option 3: Docker Compose

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8050:8050"
    volumes:
      - ./data:/app/data
      - ./src/config:/app/src/config
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
server {
    listen 80;
    server_name your-server.nhs.uk;

    location / {
        proxy_pass http://localhost:8050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/pathway-analysis /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## Process Management

### Systemd (Linux)

```ini
# /etc/systemd/system/pathway-analysis.service
[Unit]
Description=Pathway Analysis Dash App
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/pathway-analysis
ExecStart=/opt/pathway-analysis/.venv/bin/gunicorn dash_app.app:server -b 0.0.0.0:8050 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pathway-analysis
sudo systemctl start pathway-analysis
```

### Windows Service

Use NSSM (Non-Sucking Service Manager) on Windows:

```powershell
# Install NSSM
choco install nssm

# Create service
nssm install PathwayAnalysis "C:\Path\To\python.exe" "run_dash.py"
nssm set PathwayAnalysis AppDirectory "C:\Path\To\pathway-analysis"
nssm start PathwayAnalysis
```

## Environment Configuration

### Production Environment Variables

```bash
# Database path (if using custom location)
export PATHWAY_DB_PATH=/var/data/pathways.db

# Snowflake (for data refresh only — not needed for the web app)
export SNOWFLAKE_ACCOUNT=your-account
export SNOWFLAKE_WAREHOUSE=your-warehouse
```

### Snowflake Configuration

Snowflake is only needed for the data refresh CLI command, not for running the web application. Ensure `src/config/snowflake.toml` is configured:

```toml
[snowflake]
account = "your-production-account"
warehouse = "ANALYTICS_WH"
database = "DATA_HUB"
schema = "CDM"
authenticator = "externalbrowser"
```

## Data Refresh

The web application reads pre-computed data from SQLite. To update the data:

```bash
# Full refresh (both chart types, all date filters)
python -m cli.refresh_pathways --chart-type all

# The app will serve new data immediately — no restart needed
```

Schedule this as a cron job or Windows Task Scheduler task for periodic updates.

## Security Considerations

### Network Security

1. **Firewall Rules**: Only expose port 8050 (or 80/443 behind reverse proxy)
2. **HTTPS**: Use TLS certificates via reverse proxy (nginx, Caddy)
3. **VPN**: Consider restricting access to NHS network only

### Data Security

1. **Database Access**: The app uses read-only SQLite access
2. **No file uploads**: The Dash app does not accept file uploads
3. **No authentication built in**: Add authentication via reverse proxy or middleware if needed

## Monitoring

### Health Checks

The application serves at `/` — a 200 response indicates the app is running.

### Logging

Dash outputs request logs to stdout. Configure log aggregation as needed:

```bash
# Redirect logs to file
gunicorn dash_app.app:server -b 0.0.0.0:8050 --access-logfile /var/log/pathway-analysis/access.log --error-logfile /var/log/pathway-analysis/error.log
```

## Troubleshooting

### Port already in use

```bash
# Find process using port 8050
lsof -i :8050   # Linux/macOS
netstat -ano | findstr :8050   # Windows
```

### Database not found

```bash
# Verify database exists
ls -la data/pathways.db
sqlite3 data/pathways.db ".tables"

# Recreate if needed
python -m data_processing.migrate
python -m cli.refresh_pathways --chart-type all
```

### Import errors

```bash
# Ensure src/ is on Python path
uv run python setup_dev.py

# Verify imports
uv run python -c "from dash_app.app import app; print('OK')"
```

---

## Quick Reference

| Environment | Command | Port |
|-------------|---------|------|
| Development | `python run_dash.py` | 8050 |
| Production | `gunicorn dash_app.app:server -b 0.0.0.0:8050 --workers 4` | 8050 |
| Docker | `docker run -p 8050:8050 pathway-analysis` | 8050 |

For more information, see:
- [Dash Documentation](https://dash.plotly.com/)
- [Gunicorn Deployment](https://docs.gunicorn.org/en/stable/deploy.html)
