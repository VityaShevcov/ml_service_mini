# 🏗️ Architecture Documentation

This document provides a comprehensive overview of the ML Chat Billing Service architecture, design decisions, and implementation details.

## 📂 Project Structure

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

## 📊 System Overview

The ML Chat Billing Service is a microservices-based application that provides AI-powered chat functionality with integrated billing and user management.

### Key Features
- **Multi-Backend AI**: Support for both Ollama (local) and HuggingFace (cloud) models
- **Intelligent Fallbacks**: Automatic fallback to alternative models when primary models unavailable
- **Performance Optimized**: Lazy loading, caching, and memory optimization
- **Comprehensive Testing**: Unit, integration, and script-based testing
- **Docker Ready**: Complete containerization support
- **Monitoring**: Real-time performance monitoring and health checks

### High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Gradio UI     │    │   FastAPI       │    │   Database      │
│   (Frontend)    │◄──►│   (Backend)     │◄──►│   (SQLite)      │
│   Port: 7861    │    │   Port: 7860    │    │   Local File    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │  ML Backend     │              │
         └──────────────►│  (Ollama/Local) │              │
                        │   Fast GPU/CPU  │              │
                        └─────────────────┘              │
                                 │                       │
                        ┌─────────────────┐              │
                        │   Alternative   │◄─────────────┘
                        │   HuggingFace   │
                        │   (Fallback)    │
                        └─────────────────┘
```

## 🏛️ Core Components

### 1. API Layer (`app/api/`)

#### FastAPI Application (`main.py`)
- **Purpose**: Main application entry point
- **Responsibilities**: 
  - Route registration
  - Middleware configuration
  - CORS handling
  - Application lifecycle management

#### API Routers
- **Auth Router** (`auth.py`): User authentication and registration
- **Chat Router** (`chat.py`): Chat functionality and model interaction
- **Billing Router** (`billing.py`): Credit management and transactions
- **ML Router** (`ml.py`): Model management and inference
- **Monitoring Router** (`monitoring.py`): System monitoring and health checks
- **Admin Router** (`admin.py`): Administrative functions
- **Performance Router** (`performance.py`): Performance monitoring and optimization

#### Middleware Stack
```
Request → Security Headers → Performance Monitoring → Memory Monitoring → 
Health Check → Auth Logging → General Logging → Rate Limiting → CORS → Application
```

### 2. Service Layer (`app/services/`)

#### User Service (`user_service.py`)
```python
class UserService:
    - register_user()      # User registration with validation
    - authenticate_user()  # Login and JWT token generation
    - refresh_token()      # Token refresh mechanism
    - get_user_profile()   # User profile management
```

#### Billing Service (`billing_service.py`)
```python
class BillingService:
    - add_credits()        # Credit addition with transaction logging
    - charge_credits()     # Credit deduction with atomic operations
    - get_balance()        # Current balance retrieval
    - get_transactions()   # Transaction history
```

#### Chat Service (`chat_service.py`)
```python
class ChatService:
    - send_message()       # Message processing with billing integration
    - validate_message()   # Input validation and sanitization
    - get_history()        # Chat history with filtering
    - get_statistics()     # Usage statistics
```

#### Monitoring Service (`monitoring_service.py`)
```python
class MonitoringService:
    - get_system_metrics() # System resource monitoring
    - get_usage_analytics() # Usage pattern analysis
    - generate_reports()   # Report generation
    - get_health_status()  # Health status assessment
```

### 3. ML Layer (`app/ml/`)

#### Model Loader (`model_loader.py`)
```python
class ModelLoader:
    - load_gemma3_1b()     # Load 1B parameter model
    - load_gemma3_12b()    # Load 12B parameter model with quantization
    - unload_model()       # Memory cleanup
    - get_model_info()     # Model metadata
```

#### ML Service (`ml_service.py`)
```python
class MLService:
    - generate_response()  # Text generation with Ollama/HuggingFace
    - get_available_models() # Available model listing with fallbacks
    - get_model_cost()     # Cost calculation per model
    - initialize_models()  # Model initialization with lazy loading
    - reload_model()       # Dynamic model switching
    - get_system_status()  # System health and performance metrics

# Supported Backends:
- Ollama (Local): Fast inference with llama3.2 fallback
- HuggingFace: Cloud models with quantization support
```

#### Model Loader (`model_loader.py`)
```python
class ModelLoader:
    - load_gemma3_1b()     # Load 1B parameter model
    - load_gemma3_4b()     # Load 4B parameter model
    - unload_model()       # Memory cleanup
    - get_model_info()     # Model metadata
    - optimize_memory()    # Memory optimization
    - get_memory_usage()   # Memory statistics
```

### 4. Data Layer (`app/models/`)

#### Database Models
```python
# Core entities
User                 # User accounts and authentication
CreditTransaction    # Billing transactions
ModelInteraction     # Chat history and usage
UserSession         # Session management (optional)

# Relationships
User 1:N CreditTransaction
User 1:N ModelInteraction
User 1:N UserSession
```

#### CRUD Operations (`crud.py`)
```python
class UserCRUD:
    - create(), get_by_id(), get_by_email(), update_credits()

class CreditTransactionCRUD:
    - create(), get_by_user(), get_by_type()

class ModelInteractionCRUD:
    - create(), get_by_user(), get_recent()
```

### 5. UI Layer (`app/ui/`)

#### Gradio Interfaces
- **Main Interface** (`main_interface.py`): Application orchestration
- **Auth Interface** (`auth_interface.py`): Login and registration
- **Chat Interface** (`chat_interface.py`): Chat functionality
- **Credits Interface** (`credits_interface.py`): Credit management
- **History Interface** (`history_interface.py`): Chat history and analytics
- **Admin Interface** (`admin_interface.py`): Administrative functions

## 🔄 Data Flow

### 1. User Authentication Flow
```
User Input → Auth Interface → Auth API → User Service → Database → JWT Token → UI Update
```

### 2. Chat Message Flow
```
User Message → Chat Interface → Chat API → Chat Service → Billing Check → 
ML Service → Model Inference → Response → Billing Charge → Database → UI Update
```

### 3. Credit Management Flow
```
Credit Request → Credits Interface → Billing API → Billing Service → 
Transaction Creation → Database Update → Balance Update → UI Refresh
```

## 🧠 ML Architecture

### Model Management Strategy

#### Lazy Loading
- Models loaded on first request
- Memory-efficient initialization
- Fallback mechanisms for failures

#### Caching Strategy
```python
# Three-tier caching system
1. Response Cache (LRU + TTL)
   - Key: hash(prompt + model + parameters)
   - Size: 1000 entries
   - TTL: 24 hours

2. Model Cache (LRU)
   - Key: model_name
   - Size: 2 models max
   - Eviction: Least recently used

3. System Cache (Memory cleanup)
   - Automatic garbage collection
   - GPU memory management
   - Background cleanup threads
```

#### Memory Management
```python
class MemoryManager:
    - Monitor system resources (CPU, RAM, GPU)
    - Trigger cleanup at 85% threshold
    - Automatic model eviction
    - Background optimization
```

### Model Configuration
```python
# Primary Models (Gemma3 with Ollama backend)
- Gemma3 1B → Llama3.2:1B
  - Parameters: ~1 billion
  - Memory: ~2GB RAM
  - Cost: 1 credit per message
  - Backend: Ollama (local)

- Gemma3 4B → Llama3.2:3B
  - Parameters: ~3 billion
  - Memory: ~4GB RAM
  - Cost: 3 credits per message
  - Backend: Ollama (local)

# Fallback Models (HuggingFace)
- HuggingFace Transformers
  - Quantization: int8/4-bit available
  - Memory: Optimized with CPU offloading
  - Cost: Same as primary models
  - Backend: Cloud-based
```

## 💾 Database Design

### Schema Overview
```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    credits INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Credit transactions
CREATE TABLE credit_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    amount INTEGER NOT NULL,
    transaction_type VARCHAR(20) NOT NULL, -- 'add' or 'charge'
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Model interactions
CREATE TABLE model_interactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    model_name VARCHAR(50) NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT,
    credits_charged INTEGER NOT NULL,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Indexing Strategy
```sql
-- Performance indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_credit_transactions_user_id ON credit_transactions(user_id);
CREATE INDEX idx_credit_transactions_created_at ON credit_transactions(created_at);
CREATE INDEX idx_model_interactions_user_id ON model_interactions(user_id);
CREATE INDEX idx_model_interactions_created_at ON model_interactions(created_at);
CREATE INDEX idx_model_interactions_model_name ON model_interactions(model_name);
```

## 🔐 Security Architecture

### Authentication & Authorization
```python
# JWT Token Structure
{
    "sub": user_id,
    "username": "user123",
    "exp": expiration_timestamp,
    "iat": issued_at_timestamp,
    "type": "access" | "refresh"
}

# Security Layers
1. Password hashing (bcrypt with salt)
2. JWT token validation
3. Role-based access control
4. Rate limiting per IP
5. Input validation and sanitization
6. SQL injection prevention
```

### API Security
- **HTTPS enforcement** in production
- **CORS configuration** for cross-origin requests
- **Security headers** (HSTS, CSP, X-Frame-Options)
- **Rate limiting** to prevent abuse
- **Input validation** on all endpoints
- **Error handling** without information leakage

## 📊 Monitoring Architecture

### Performance Monitoring
```python
# Metrics Collection
class PerformanceMetrics:
    - Request latency (p50, p95, p99)
    - Throughput (requests per second)
    - Error rates by endpoint
    - Resource utilization (CPU, memory, GPU)
    - Model inference times
    - Cache hit rates
```

### System Monitoring
```python
# Resource Monitoring
class SystemMonitor:
    - CPU usage and load average
    - Memory usage (RAM and GPU)
    - Disk usage and I/O
    - Network statistics
    - Process monitoring
    - Health checks
```

### Alerting System
```python
# Alert Conditions
- Memory usage > 90%
- CPU usage > 95% for 5+ minutes
- Error rate > 5%
- Response time > 10 seconds
- Disk usage > 90%
- Model loading failures
```

## 🚀 Performance Optimizations

### Response Time Optimization
1. **Response Caching**: Cache frequent prompt/response pairs
2. **Model Caching**: Keep models in memory with LRU eviction
3. **Connection Pooling**: Reuse database connections
4. **Async Processing**: Non-blocking I/O operations
5. **Lazy Loading**: Load resources on demand

### Memory Optimization
1. **Model Quantization**: int8 quantization for large models
2. **Garbage Collection**: Automatic memory cleanup
3. **Memory Monitoring**: Real-time usage tracking
4. **Smart Eviction**: LRU-based model eviction
5. **Background Cleanup**: Periodic memory optimization

### Scalability Considerations
1. **Horizontal Scaling**: Multiple API instances behind load balancer
2. **Database Scaling**: Read replicas and connection pooling
3. **Caching Layer**: Redis for distributed caching
4. **Model Serving**: Separate model inference services
5. **Queue System**: Async task processing with Celery

## 🔧 Configuration Management

### Environment-Based Configuration
```python
# Development
DEBUG = True
DATABASE_URL = "sqlite:///dev.db"
LOG_LEVEL = "DEBUG"
ENABLE_CACHING = False

# Production
DEBUG = False
DATABASE_URL = "postgresql://..."
LOG_LEVEL = "WARNING"
ENABLE_CACHING = True
ENABLE_MONITORING = True
```

### Feature Flags
```python
# Runtime configuration
FEATURES = {
    "response_caching": True,
    "model_quantization": True,
    "performance_monitoring": True,
    "rate_limiting": True,
    "admin_panel": True
}
```

## 📈 Deployment Architecture

### Container Strategy
```dockerfile
# Multi-stage build
FROM python:3.9-slim as base
# ... base dependencies

FROM base as development
# ... development tools

FROM base as production
# ... production optimizations
```

### Service Orchestration
```yaml
# Docker Compose services
services:
  ml-chat-service:    # Main application
  db:                 # PostgreSQL database
  redis:              # Caching layer
  nginx:              # Reverse proxy
  prometheus:         # Metrics collection
  grafana:            # Monitoring dashboard
```

## 🔄 Future Enhancements

### Planned Improvements
1. **Model Serving**: Dedicated model inference services
2. **Distributed Caching**: Redis cluster for caching
3. **Message Queues**: Async processing with RabbitMQ/Redis
4. **API Gateway**: Centralized routing and rate limiting
5. **Microservices**: Split into smaller, focused services
6. **Auto-scaling**: Kubernetes-based auto-scaling
7. **Advanced Monitoring**: Distributed tracing with Jaeger
8. **CI/CD Pipeline**: Automated testing and deployment

### Scalability Roadmap
1. **Phase 1**: Optimize current monolith
2. **Phase 2**: Extract model serving
3. **Phase 3**: Microservices architecture
4. **Phase 4**: Multi-region deployment
5. **Phase 5**: Edge computing integration

---

This architecture is designed to be **scalable**, **maintainable**, and **performant** while providing a solid foundation for future enhancements and growth.