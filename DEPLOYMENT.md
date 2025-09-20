# 🚀 Deployment Guide

This guide covers different deployment options for the ML Chat Billing Service.

## 📋 Prerequisites

### System Requirements
- **CPU**: 4+ cores recommended
- **RAM**: 8GB minimum, 16GB+ recommended (for 12B model)
- **Storage**: 20GB+ free space
- **GPU**: CUDA-compatible GPU (optional, for better performance)

### Software Requirements
- **Python**: 3.8+ (for local deployment)
- **Docker**: 20.10+ (for containerized deployment)
- **Docker Compose**: 2.0+ (for multi-container deployment)

## 🏠 Local Development Deployment

### Quick Start
```bash
# 1. Clone repository
git clone <repository-url>
cd ml-chat-billing-service

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment (optional)
cp .env.example .env
# Edit .env with your configuration

# 4. Start service
python startup.py
```

### Manual Setup
```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize database
python -c "from app.database import engine; from app.models import Base; Base.metadata.create_all(bind=engine)"

# 4. Start API server
python startup.py --mode api

# 5. Start Gradio UI (in another terminal)
python startup.py --mode ui
```

## 🐳 Docker Deployment

### Simple Docker Deployment
```bash
# 1. Build and start services
docker-compose up -d

# 2. Check status
docker-compose ps

# 3. View logs
docker-compose logs -f ml-chat-service

# 4. Stop services
docker-compose down
```

### Using Deployment Script
```bash
# Make script executable (Linux/Mac)
chmod +x deploy.sh

# Deploy with Docker
./deploy.sh docker

# Check status
./deploy.sh status

# View logs
./deploy.sh logs

# Stop services
./deploy.sh stop
```

## 🏭 Production Deployment

### Production Setup
```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with production values:
# - Set DEBUG=false
# - Use PostgreSQL DATABASE_URL
# - Set secure SECRET_KEY and JWT_SECRET_KEY
# - Configure SSL settings

# 2. Generate SSL certificates
openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes

# 3. Deploy with production profile
docker-compose --profile production up -d

# 4. Verify deployment
curl -k https://localhost/health
```

### Production Checklist
- [ ] Set secure environment variables
- [ ] Use PostgreSQL or MySQL database
- [ ] Configure SSL/TLS certificates
- [ ] Set up reverse proxy (Nginx)
- [ ] Configure monitoring and logging
- [ ] Set up backup procedures
- [ ] Configure firewall rules
- [ ] Set up domain and DNS

## 📊 Monitoring Deployment

### Enable Monitoring Stack
```bash
# Deploy with monitoring
docker-compose --profile monitoring up -d

# Access monitoring services
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

### Monitoring Configuration
1. **Prometheus**: Metrics collection and alerting
2. **Grafana**: Visualization and dashboards
3. **Application Metrics**: Built-in performance monitoring

## 🔧 Configuration

### Environment Variables
Key environment variables for production:

```bash
# Security
SECRET_KEY=your-super-secret-key
JWT_SECRET_KEY=your-jwt-secret-key
DEBUG=false

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Performance
MEMORY_CLEANUP_THRESHOLD=0.85
RATE_LIMIT_REQUESTS_PER_MINUTE=60
ENABLE_RESPONSE_CACHING=true

# Monitoring
ENABLE_SYSTEM_MONITORING=true
ENABLE_PERFORMANCE_MONITORING=true
```

### Database Configuration

#### PostgreSQL (Recommended)
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/ml_chat_service
```

#### MySQL
```bash
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/ml_chat_service
```

#### SQLite (Development only)
```bash
DATABASE_URL=sqlite:///./ml_chat_service.db
```

## 🔒 Security Configuration

### SSL/TLS Setup
```bash
# Generate self-signed certificate (development)
openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes

# For production, use certificates from a CA like Let's Encrypt
certbot certonly --standalone -d yourdomain.com
```

### Firewall Configuration
```bash
# Allow HTTP and HTTPS
sudo ufw allow 80
sudo ufw allow 443

# Allow SSH (if needed)
sudo ufw allow 22

# Enable firewall
sudo ufw enable
```

## 📈 Performance Optimization

### Memory Optimization
- Enable lazy model loading
- Configure model cache size
- Set memory cleanup thresholds
- Use GPU if available

### Response Optimization
- Enable response caching
- Configure cache TTL
- Use connection pooling
- Enable compression

### Database Optimization
- Use connection pooling
- Configure appropriate indexes
- Regular maintenance and backups
- Monitor query performance

## 🔄 Backup and Recovery

### Database Backup
```bash
# PostgreSQL backup
docker-compose exec db pg_dump -U postgres ml_chat_service > backup.sql

# Restore from backup
docker-compose exec -T db psql -U postgres ml_chat_service < backup.sql
```

### Automated Backups
```bash
# Add to crontab for daily backups
0 2 * * * /path/to/deploy.sh backup
```

## 🚨 Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Check what's using the port
netstat -tulpn | grep :8000

# Kill process using port
sudo kill -9 <PID>
```

#### Memory Issues
```bash
# Check memory usage
free -h

# Check Docker memory usage
docker stats

# Clear Docker cache
docker system prune -f
```

#### Database Connection Issues
```bash
# Check database container
docker-compose logs db

# Test database connection
docker-compose exec db psql -U postgres -d ml_chat_service -c "SELECT 1;"
```

#### Model Loading Issues
```bash
# Check available memory
free -h

# Check GPU memory (if using GPU)
nvidia-smi

# Check model loading logs
docker-compose logs ml-chat-service | grep -i model
```

### Log Analysis
```bash
# View application logs
docker-compose logs -f ml-chat-service

# View specific service logs
docker-compose logs -f db
docker-compose logs -f redis

# View system logs
journalctl -u docker
```

## 📞 Support

### Health Checks
- API Health: `GET /health`
- System Status: `GET /monitoring/health`
- Performance Metrics: `GET /performance/metrics`

### Monitoring Endpoints
- System Metrics: `GET /monitoring/metrics`
- Performance Analysis: `GET /performance/analysis`
- Usage Analytics: `GET /monitoring/analytics`

### Getting Help
1. Check the logs for error messages
2. Verify environment configuration
3. Check system resources (CPU, memory, disk)
4. Review the troubleshooting section
5. Check GitHub issues or create a new one

---

**For additional support, please refer to the main README.md or create an issue on GitHub.**