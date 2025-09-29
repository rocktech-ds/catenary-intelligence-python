# Claude AI Assistant Instructions - Catenary Project

## 📋 Project Overview

**Project Name**: Catenary - Advanced Document Analysis System
**Primary Focus**: Engineering document analysis for railway/infrastructure projects
**Tech Stack**: Python (FastAPI backend) + TypeScript/React (frontend)
**Current Status**: 15 advanced extractors implemented, VPS-ready architecture

## 🎯 Project Goals

1. **Primary**: Build the most advanced engineering document analysis system
2. **Focus**: Railway engineering documents (Portuguese/English)
3. **Architecture**: VPS-friendly, cost-effective, high-performance
4. **Quality**: Production-ready with comprehensive testing and documentation

## 📁 Project Structure

```
catenary/
├── python-analyzer/
│   ├── intelligence/
│   │   ├── extractors/          # All extractor modules
│   │   ├── services/            # Core services (enhanced_analysis_service.py)
│   │   ├── models/              # Data models and schemas
│   │   └── utils/               # Utility functions
│   ├── api/                     # FastAPI endpoints
│   └── frontend_analysis_types.json  # Frontend configuration
├── src/                         # Frontend React/TypeScript
├── IMPLEMENTATION_STATUS.md     # Current progress tracking
├── docs/                        # Project documentation
└── CLAUDE_INSTRUCTIONS.md       # This file
```

## 🚀 Current Implementation Status

### ✅ **COMPLETED (15 Features)**
1. **Stamp Detection** - Engineering stamps, seals, signatures
2. **Layout Analysis** - Document structure and regions
3. **Revision Tracking** - Change history and approvals
4. **Assembly Detection** - Component hierarchies and BOM
5. **Technical Specifications** - Materials, tolerances, standards
6. **Dimensional Analysis** - GD&T, measurements, coordinates
7. **Vector Graphics Analysis** - CAD symbols, geometric shapes
8. **Enhanced Table Extraction** - Multiple libraries + AI
9. **AI Consensus Analysis** - Multi-provider validation
10. **Quality Validation** - Confidence scoring and QA
11. **Robust API Integration** - FastAPI endpoints
12. **Complete Frontend Integration** - React UI controls
13. **Progressive Enhancement** - Modular architecture
14. **Error Handling & Logging** - Production-ready
15. **Performance Optimization** - VPS-friendly processing

### 📋 **REMAINING (11 Tasks)**
1. Quality validation system (backend completion)
2. Handwriting recognition extractor  
3. Multi-language processing support
4. Standards compliance checker
5. AI consensus analysis system
6. Advanced error correction system
7. Intelligent normalization system
8. Comprehensive QA system
9. Results visualization components
10. Comprehensive test suite
11. Documentation and user guides

## 🛠️ Development Guidelines

### **File Organization Principles**
- **Extractors**: `/python-analyzer/intelligence/extractors/[name]_extractor.py`
- **Services**: `/python-analyzer/intelligence/services/enhanced_analysis_service.py`
- **Models**: `/python-analyzer/intelligence/models/analysis_models.py`
- **Frontend Config**: `/python-analyzer/frontend_analysis_types.json`
- **Documentation**: Root level `.md` files

### **Code Quality Standards**
- **Type Hints**: All Python functions must have proper type hints
- **Error Handling**: Comprehensive try/catch with specific error messages
- **Logging**: Use structured logging with appropriate levels
- **Documentation**: Docstrings for all classes and methods
- **Testing**: Unit tests for all new extractors (when implementing test suite)

### **Architecture Patterns**
- **Modular Design**: Each extractor is independent and composable
- **VPS-Friendly**: Minimal external dependencies, efficient processing
- **AI Integration**: Optional AI enhancement for all extractors
- **Progressive Enhancement**: Core functionality + AI-powered improvements
- **Portuguese/English**: Bilingual support with technical terminology

### **Integration Workflow**
When implementing new extractors, always:
1. Create extractor module in `/intelligence/extractors/`
2. Add import and initialization to `enhanced_analysis_service.py`
3. Add processing step with progress tracking and error handling
4. Update `analysis_models.py` if new request/response types needed
5. Update `frontend_analysis_types.json` configuration
6. Update `IMPLEMENTATION_STATUS.md` documentation
7. Test integration with existing system

## 🎯 Priority Guidelines

### **High Priority Tasks** (Focus Areas)
1. **Advanced Extractors**: Handwriting recognition, multi-language support
2. **Quality Systems**: Comprehensive QA, error correction, normalization
3. **Standards Compliance**: Engineering standards validation
4. **Visualization**: Advanced result presentation
5. **Testing**: Comprehensive test coverage

### **Medium Priority**
1. **Performance Optimization**: Speed improvements, memory efficiency
2. **Documentation**: User guides, API documentation
3. **Deployment**: VPS deployment scripts and configurations

### **Low Priority**
1. **UI Polish**: Advanced frontend features
2. **Additional Languages**: Beyond Portuguese/English
3. **External Integrations**: Third-party service connections

## 🔧 Technical Preferences

### **Python Development**
- **Async/Await**: Use async patterns for I/O operations
- **Type Safety**: Leverage Pydantic models and dataclasses
- **Error Handling**: Graceful degradation with informative messages
- **Performance**: Memory-efficient processing for VPS deployment
- **Dependencies**: Prefer lightweight libraries over heavy frameworks

### **AI Integration**
- **Free Services First**: Prioritize free AI providers (Groq, Gemini, etc.)
- **Consensus Mode**: Multi-provider validation for critical extractions
- **Fallback Strategy**: Graceful operation without AI services
- **Cost Control**: Monitor and optimize AI API usage

### **Frontend Integration**
- **Configuration-Driven**: Use JSON configs for UI elements
- **Progressive Enhancement**: Core features + advanced options
- **User Experience**: Clear progress indicators and error messages
- **Responsive Design**: Mobile-friendly interface

## 📚 Knowledge Base

### **Domain Expertise**
- **Railway Engineering**: Infrastructure, electrical systems, mechanical components
- **Portuguese Technical Terms**: Standard engineering vocabulary
- **CAD Standards**: ISO, ANSI, DIN compliance requirements
- **Document Types**: Technical drawings, specifications, BOMs, revisions

### **Technical Expertise**
- **Document Processing**: PDF parsing, OCR, image processing
- **Computer Vision**: OpenCV, pattern recognition, shape detection
- **AI/ML**: Language models, consensus algorithms, confidence scoring
- **Web Development**: FastAPI, React, TypeScript integration

## 🎭 Assistant Behavior Guidelines

### **Communication Style**
- **Professional**: Technical accuracy with clear explanations
- **Bilingual**: Portuguese/English as needed for the project
- **Action-Oriented**: Focus on implementation and results
- **Documentation**: Always update relevant files after changes

### **Decision Making**
- **VPS-First**: Always consider VPS resource constraints
- **Cost-Conscious**: Prefer free/open-source solutions
- **Quality-Focused**: Robust error handling and testing
- **User-Centric**: Clear progress feedback and intuitive interfaces

### **Work Patterns**
- **Incremental Progress**: Complete features fully before moving on
- **Documentation Updates**: Always update status files after implementation
- **Integration Focus**: Ensure new features work with existing system
- **Testing Mindset**: Consider edge cases and error conditions

## 🚀 Current Session Context

**Last Major Achievement**: Vector Graphics Extractor implementation (15th feature completed)
**Next Recommended Focus**: Handwriting Recognition Extractor or Multi-language Processing Support
**System Status**: Production-ready with 15 advanced extractors, ready for VPS deployment

## 📞 Communication Protocols

### **Status Updates**
- Update `IMPLEMENTATION_STATUS.md` after completing major features
- Update `frontend_analysis_types.json` for UI changes  
- Use todo lists for complex multi-step implementations
- Provide progress summaries at logical checkpoints

### **Error Handling**
- Always provide specific error messages with context
- Include recovery suggestions for failed operations
- Log errors appropriately for debugging
- Graceful degradation when services are unavailable

---

**Last Updated**: 2025-01-17 by Claude AI Assistant
**Version**: 1.0
**Status**: Active Development - 15/26 features completed