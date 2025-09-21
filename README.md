# 🤖 ML Chat Billing Service

A comprehensive chat service powered by Gemma3 models with integrated billing, user management, and advanced monitoring capabilities.

## 🌟 Features

### 💬 Chat Functionality
- **Multiple AI Models**: Gemma3 1B/4B with Llama3.2 fallback and different pricing
- **Real-time Chat**: Interactive Gradio interface with model selection
- **Response Caching**: Intelligent caching for improved performance
- **Memory Optimization**: Advanced memory management and lazy loading
- **Ollama Integration**: Fast local LLM serving for optimal performance

### 💰 Billing System
- **Credit-based Billing**: Pay-per-use model with different costs per model
- **Multiple Top-up Options**: Predefined packages with bonus credits
- **Transaction History**: Detailed tracking of all credit operations
- **Usage Analytics**: Comprehensive usage statistics and insights

### 👥 User Management
- **Secure Authentication**: JWT-based authentication with bcrypt password hashing
- **User Registration**: Easy signup with email verification
- **Session Management**: Secure session handling and token refresh
- **Admin Panel**: Administrative interface for user and system management

### 📊 Monitoring & Analytics
- **Real-time Monitoring**: System resource monitoring (CPU, Memory, GPU)
- **Performance Metrics**: Request tracking and performance analysis
- **Usage Reports**: Detailed reports in JSON and CSV formats
- **Health Checks**: Automated health monitoring with alerts

### 🔧 Advanced Features
- **Response Caching**: LRU cache with TTL for frequently used prompts
- **Model Caching**: Intelligent model loading and memory management
- **Rate Limiting**: Configurable rate limiting to prevent abuse
- **Performance Optimization**: Automatic memory cleanup and optimization

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- 8GB+ RAM (16GB+ recommended for 12B model)
- CUDA-compatible GPU (optional, for better performance)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd ml-chat-billing-service
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables** (optional)
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Initialize and start the service**
```bash
python startup.py
```

This will:
- Initialize the database
- Create an admin user
- Start both API server and Gradio interface

### Alternative Startup Options

**Start API server only:**
```bash
python startup.py --mode api
```

**Start Gradio UI only:**
```bash
python startup.py --mode ui
```

**Skip initialization:**
```bash
python startup.py --skip-init
```

## 🌐 Service URLs

After startup, the following services will be available:

- **Gradio Interface**: http://localhost:7861 (Main user interface)
- **API Server**: http://localhost:7860 (REST API)
- **API Documentation**: http://localhost:7860/docs (Swagger UI)
- **Health Check**: http://localhost:7860/health (System health)

## 👤 Default Admin Credentials

```
Username: admin
Email: admin@example.com
Password: Admin123!
```

**⚠️ Important**: Change the admin password in production!

## 📖 API Documentation

### Authentication Endpoints
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh JWT token

### Chat Endpoints
- `POST /chat/message` - Send message to AI model
- `GET /chat/history` - Get chat history with filtering
- `GET /chat/models` - Get available models
- `GET /chat/status` - Get chat service status

### Billing Endpoints
- `GET /billing/balance` - Get current credit balance
- `POST /billing/add` - Add credits to account
- `GET /billing/transactions` - Get transaction history

### Monitoring Endpoints
- `GET /monitoring/health` - System health status
- `GET /monitoring/metrics` - System performance metrics
- `GET /monitoring/analytics` - Usage analytics
- `GET /monitoring/report` - Generate reports

### Admin Endpoints (Admin only)
- `GET /admin/dashboard` - Admin dashboard data
- `GET /admin/users` - User management
- `POST /admin/users/{id}/credits` - Adjust user credits
- `GET /admin/reports/usage` - Usage reports
- `GET /admin/reports/financial` - Financial reports

### Performance Endpoints
- `GET /performance/metrics` - Performance metrics
- `GET /performance/analysis` - Performance analysis
- `POST /performance/optimize/memory` - Trigger memory optimization

## 🏗️ Architecture

### Project Structure
```
ml-chat-billing-service/
├── app/
│   ├── api/                 # FastAPI endpoints
│   ├── ml/                  # ML model management
│   ├── models/              # Database models
│   ├── services/            # Business logic services
│   ├── ui/                  # Gradio interfaces
│   └── utils/               # Utility functions
├── tests/                   # Test suites
│   ├── integration/         # API and integration tests
│   ├── scripts/             # Test scripts and utilities
│   └── unit/                # Unit tests
├── scripts/                 # Utility scripts
├── migrations/              # Database migrations (Alembic)
├── logs/                    # Application logs
├── config.py                # Configuration settings
├── main.py                  # FastAPI application
├── startup.py               # Startup script
├── requirements.txt         # Dependencies
├── Dockerfile               # Docker configuration
└── docker-compose.yml       # Docker Compose setup
```

### Key Components

#### ML Service
- **ModelLoader**: Handles loading and management of Gemma3 models
- **MLService**: Core ML inference service with caching
- **OptimizedMLService**: Advanced service with memory optimization

#### Billing System
- **BillingService**: Credit management and transactions
- **CreditTransaction**: Transaction tracking and history
- **Atomic Operations**: Ensures billing consistency

#### User Management
- **UserService**: User registration, authentication, and management
- **JWT Authentication**: Secure token-based authentication
- **Session Management**: User session tracking

#### Monitoring
- **MonitoringService**: System and usage monitoring
- **PerformanceMonitor**: Real-time performance tracking
- **AlertSystem**: Automated alerts and notifications

## ⚙️ Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///./ml_chat_service.db

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# Server
HOST=127.0.0.1
PORT=7860
DEBUG=true

# ML Models
GEMMA3_1B_COST=1
GEMMA3_4B_COST=3
MAX_RESPONSE_LENGTH=128

# Ollama Integration
USE_OLLAMA=true
OLLAMA_BASE_URL=http://127.0.0.1:11434

# Logging
LOG_LEVEL=INFO
```

### Model Configuration

The service supports multiple AI models with intelligent fallback:

- **Gemma3 1B** → Llama3.2:1B (1 credit per message)
- **Gemma3 4B** → Llama3.2:3B (3 credits per message)

**Backend Options:**
- **Ollama** (Recommended): Fast local serving for optimal performance
- **HuggingFace**: Cloud-based models with quantization support

Models are loaded on-demand with intelligent memory management.

## 🧪 Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Test scripts only
pytest tests/scripts/

# Run all tests
pytest tests/

# With coverage
pytest --cov=app tests/
```

### Test Categories
- **Unit Tests** (`tests/unit/`): Individual component testing
- **Integration Tests** (`tests/integration/`): API endpoint and system testing
- **Test Scripts** (`tests/scripts/`): Utility scripts for testing specific functionality

## 📊 Monitoring & Observability

### Health Monitoring
- System resource monitoring (CPU, Memory, Disk, GPU)
- Application health checks
- Performance metrics collection
- Automated alerting

### Usage Analytics
- Model usage statistics
- User activity tracking
- Credit consumption analysis
- Performance optimization recommendations

### Logging
- Structured logging with JSON format
- Request/response logging
- Error tracking and alerting
- Performance metrics logging

## 🔒 Security

### Authentication & Authorization
- JWT-based authentication
- Bcrypt password hashing
- Role-based access control (Admin/User)
- Session management

### API Security
- Rate limiting
- Input validation
- SQL injection prevention
- XSS protection

### Data Protection
- Secure credential storage
- Transaction integrity
- Audit logging
- Privacy compliance

## 🚀 Deployment

### Development
```bash
python startup.py
```

### Production

1. **Set production environment variables**
2. **Use production database** (PostgreSQL recommended)
3. **Configure reverse proxy** (nginx recommended)
4. **Set up SSL/TLS certificates**
5. **Configure monitoring and logging**

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build and run individual services
docker build -t ml-chat-service .
docker run -p 7860:7860 -p 7861:7861 ml-chat-service
```

## 📈 Performance Optimization

### Memory Management
- Lazy model loading with on-demand initialization
- LRU model caching with intelligent eviction
- Automatic memory cleanup and garbage collection
- GPU memory optimization with device mapping
- CPU offloading for large models

### Response Optimization
- Response caching with TTL for frequently asked questions
- Request deduplication to prevent duplicate processing
- Batch processing support for multiple requests
- Connection pooling for database and external services
- Optimized token generation with early stopping

### Monitoring & Alerts
- Real-time performance monitoring with structured logging
- Automated optimization triggers based on system metrics
- Resource usage alerts (CPU, memory, disk)
- Performance recommendations based on usage patterns
- Health checks with automatic recovery

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run linting
flake8 app/
black app/

# Run type checking
mypy app/
```

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Common Issues

**Q: Models not loading?**
A: Ensure you have sufficient RAM (8GB+ for 1B, 16GB+ for 12B model)

**Q: Database connection errors?**
A: Check DATABASE_URL environment variable and database permissions

**Q: High memory usage?**
A: Enable memory optimization in settings or use smaller models

**Q: Slow responses?**
A: Enable response caching and check system resources

### Getting Help

- Check the [API documentation](http://localhost:8000/docs)
- Review the logs for error messages
- Check system resource usage
- Verify environment configuration

### Reporting Issues

Please include:
- System specifications
- Error messages and logs
- Steps to reproduce
- Expected vs actual behavior

## 🔄 Changelog

### v1.0.0
- Initial release
- Gemma3 model integration
- Credit-based billing system
- User management and authentication
- Gradio web interface
- Monitoring and analytics
- Performance optimization
- Comprehensive testing

---

**Built with ❤️ using FastAPI, Gradio, and Transformers**