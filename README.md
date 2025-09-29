# 🧠 Catenary Intelligence - Python Analysis Service

An advanced document analysis service powered by AI and machine learning, specialized in technical drawings and engineering documents. Production-ready microservice with real-time processing capabilities.

## ✨ Features

### Core Analysis Capabilities
- 🤖 **Multi-provider AI analysis** (Gemini, Groq, X.AI, OpenAI)
- 📄 **Advanced PDF extraction** with multiple engines (PyMuPDF, PDFPlumber)
- 🔍 **Intelligent OCR** with Tesseract integration
- 🔧 **Component & BOM detection** for technical drawings
- 📐 **Dimensional analysis** for engineering documents
- 🏷️ **Revision tracking** and stamp detection
- 📊 **Table extraction** with advanced algorithms

### Technical Features
- 💾 **PostgreSQL integration** with asyncpg for high performance
- 🚀 **Async processing** with FastAPI and background tasks
- 📡 **WebSocket support** for real-time progress updates
- 🔄 **Microservices architecture** Docker-ready
- 📊 **Structured output** ready for UI consumption
- ⚡ **High performance** with concurrent job processing

## Quick Start

1. Copy `.env.example` to `.env` and add your keys
2. Run with Docker Compose:

```bash
docker-compose up -d
```

## API Endpoints

### Main Endpoint (Unified)
- `POST /analyze` - Complete document analysis
  - Accepts text or file_url
  - Returns job_id for async processing

### Get Results
- `GET /analysis/{job_id}` - Get analysis results
- `GET /analyses/recent` - Get recent analyses from database

## Environment Variables

Required:
- `GEMINI_API_KEY` - Google Gemini API key
- `GROQ_API_KEY` - Groq API key  
- `DATABASE_URL` - PostgreSQL connection string

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn main:app --reload --port 8003
```

## Testing

```bash
# Test the API
curl -X POST http://localhost:8002/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Sample document text"}'
```

## Sync with VPS

This code is synchronized with the production deployment at `204.44.123.122:8002`
