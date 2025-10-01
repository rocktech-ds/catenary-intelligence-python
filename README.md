# Catenary Intelligence Python Service

🧠 FastAPI-based intelligence service for technical drawing analysis and component detection.

## 🚀 Quick Start

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python main.py
```

### Docker Development
```bash
# Build and run with Docker Compose
docker compose up --build
```

## 📡 API Endpoints

- `GET /health` - Health check endpoint
- `POST /analyze` - Analyze technical drawings
- `GET /docs` - Interactive API documentation
- `GET /redoc` - Alternative API documentation

## 🔧 Configuration

### Environment Variables
Create a `.env` file with the following variables:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@host:port/database

# Intelligence Service Configuration
INTELLIGENCE_PORT=8003
INTELLIGENCE_HOST=0.0.0.0

# External API Configuration
OPENAI_API_KEY=your_openai_api_key
GOOGLE_GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
XAI_API_KEY=your_xai_api_key
```

## 🏗️ Deployment

### Automatic Deployment (GitHub Actions)
The service automatically deploys to the VPS when changes are pushed to the `main` branch.

### Manual Deployment
```bash
# On the VPS
cd /root/catenary-intelligence
./deploy.sh
```

## 🐳 Docker Configuration

The service runs in a Docker container with:
- **Internal Port**: 8003 (container)
- **External Port**: 8002 (host)
- **Network**: Connected to `catenary-network` for internal communication
- **Health Check**: Available at `/health` endpoint

## 📊 Service Architecture

```
GitHub Repository (main branch)
        ↓ (Push triggers deployment)
GitHub Actions Workflow
        ↓ (SSH deployment)
VPS (204.44.123.122)
        ↓ (Docker deployment)
Catenary Intelligence Service
        ↓ (Internal network: 8003)
Container Network (catenary-network)
        ↓ (External access: 8002)
Public API Access
```

## 🏥 Health Monitoring

- **Internal Health**: `http://localhost:8003/health`
- **External Health**: `http://204.44.123.122:8002/health`
- **Logs**: `docker compose logs -f catenary-intelligence`

## 🔧 Troubleshooting

### Service Not Starting
```bash
# Check container status
docker compose ps

# View logs
docker compose logs catenary-intelligence

# Restart service
docker compose restart catenary-intelligence
```

### Health Check Failures
```bash
# Test internal connectivity
curl http://localhost:8003/health

# Test external connectivity
curl http://204.44.123.122:8002/health

# Check network connectivity
docker network inspect catenary-network
```

### Database Connection Issues
```bash
# Test database connectivity
python test_db_function.py

# Check database logs
docker compose logs catenary-db
```

## 🚧 Development

### Adding New Analyzers
1. Create analyzer in `analyzers/` directory
2. Import and register in `main.py`
3. Add tests and documentation
4. Deploy via GitHub Actions

### API Development
- FastAPI framework with automatic OpenAPI documentation
- Async/await pattern for I/O operations
- SQLAlchemy for database operations
- Pydantic models for request/response validation

## 📝 Logs

View service logs:
```bash
# Real-time logs
docker compose logs -f catenary-intelligence

# Last 100 lines
docker compose logs --tail=100 catenary-intelligence

# Logs with timestamps
docker compose logs -t catenary-intelligence
```

---

🔗 **Service URL**: http://204.44.123.122:8002
🏥 **Health Check**: http://204.44.123.122:8002/health
📚 **API Docs**: http://204.44.123.122:8002/docs