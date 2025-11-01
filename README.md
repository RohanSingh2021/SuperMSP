# Super MSP Deploy System

A comprehensive Managed Service Provider (MSP) platform that combines intelligent ticket processing, financial analytics, license management, and AI-powered insights to streamline IT service operations.

## 🏗️ System Architecture

This system consists of two main components:

### Backend (`Agents/`)
- **Python-based FastAPI application** serving as the core engine
- **Multi-agent AI system** for intelligent decision making
- **Real-time WebSocket communication** for live updates
- **SQLite database** for data persistence
- **ChromaDB vector store** for RAG (Retrieval Augmented Generation)

### Frontend (`Frontend/`)
- **React + Vite application** providing the user interface
- **Real-time dashboard** with WebSocket integration
- **Interactive charts and analytics** using Recharts
- **Responsive design** for desktop and mobile

## 📁 Project Structure

```
Super-MSP-Deploy-30-Oct/
├── Agents/                          # Backend Python Application
│   ├── main.py                      # Core ticket processing logic & system orchestration
│   ├── api.py                       # FastAPI REST endpoints & WebSocket handlers
│   ├── chatbot_orchestrator.py      # AI agent coordination & query routing
│   ├── websocket_manager.py         # Real-time communication management
│   ├── email_agent.py               # Email automation & notifications
│   ├── file_generator.py            # PDF/Excel report generation
│   ├── negotiation_orchestrator.py  # Contract negotiation analysis
│   ├── software_recommendation.py   # AI-powered software suggestions
│   ├── prediction.py                # Revenue forecasting models
│   ├── requirements.txt             # Python dependencies
│   │
│   ├── agents/                      # Specialized AI Agents
│   │   ├── rag_agent.py            # Document retrieval & knowledge base
│   │   ├── sla_agent.py            # Service Level Agreement validation
│   │   ├── scheduler.py            # Ticket assignment & JIRA integration
│   │   ├── technician_agent.py     # Technician workload management
│   │   ├── human_approval.py       # Human-in-the-loop approval system
│   │   └── search_agent.py         # LinkedIn/company contact discovery
│   │
│   ├── src/                        # Core Business Logic
│   │   ├── agents/                 # Business Intelligence Agents
│   │   │   ├── financial_agent.py          # Billing & payment analytics
│   │   │   ├── license_audit_agent.py      # Software license compliance
│   │   │   ├── company_specific_ticket_agent.py  # Customer support metrics
│   │   │   └── msp_insights_agent.py       # Cross-domain business intelligence
│   │   ├── computations/           # Data Processing Engines
│   │   │   ├── financial_data_generator.py     # Financial calculations
│   │   │   ├── license_audit_data_generator.py # License usage analysis
│   │   │   └── company_ticket_data_generator.py # Ticket analytics
│   │   └── utils/                  # Shared Utilities
│   │       ├── llm_wrapper.py      # AI model integration
│   │       ├── summarizer.py       # Content summarization
│   │       └── file_utils.py       # File operations
│   │
│   ├── data/                       # Data Storage
│   │   ├── tickets.json            # Sample ticket data
│   │   ├── revenue_data.json       # Financial records
│   │   ├── sla_sample.txt          # SLA agreement templates
│   │   ├── chroma/                 # Vector database for RAG
│   │   └── generic_queries/        # Knowledge base Q&A
│   │
│   ├── databases/                  # SQLite Database
│   │   └── msp_data.db            # Main application database
│   │
│   ├── models/                     # ML Models & Processed Data
│   ├── output/                     # Generated Analytics Files
│   ├── exports/                    # PDF/Excel Reports
│   ├── uploads/                    # File Upload Storage
│   └── negotiation_results/        # Contract Analysis Results
│
└── Frontend/                       # React Frontend Application
    ├── src/
    │   ├── App.jsx                 # Main application component
    │   ├── config.js               # API configuration
    │   ├── components/             # React Components
    │   │   ├── Dashboard.jsx           # Main dashboard
    │   │   ├── AgentsPage.jsx          # AI agents interface
    │   │   ├── ClientsOverview.jsx     # Customer management
    │   │   ├── ChatbotWidget.jsx       # AI assistant interface
    │   │   ├── RevenuePredictionChart.jsx # Financial forecasting
    │   │   └── ClientDetail/           # Customer detail views
    │   ├── hooks/                  # Custom React Hooks
    │   │   └── useTicketWebSocket.js   # WebSocket integration
    │   └── styles/                 # CSS Stylesheets
    ├── public/                     # Static Assets
    ├── package.json               # Node.js dependencies
    └── vite.config.js             # Build configuration
```

## 🚀 Key Features

### 1. Intelligent Ticket Processing (`main.py`)
- **Automated SLA validation** using AI-powered analysis
- **RAG-based knowledge retrieval** for instant solutions
- **Human-in-the-loop approval** for complex cases
- **Real-time processing timeline** with WebSocket updates
- **Automatic technician assignment** based on expertise

### 2. Comprehensive API Layer (`api.py`)
- **50+ REST endpoints** for complete system functionality
- **WebSocket support** for real-time updates
- **File upload/download** capabilities
- **Multi-format exports** (PDF, Excel)
- **Authentication & security** middleware

### 3. Multi-Agent AI System (`chatbot_orchestrator.py`)
- **Query analysis & routing** to specialized agents
- **Parallel agent execution** for complex queries
- **Strategic business insights** synthesis
- **Rate limiting & error handling**
- **Slash command support** (/pdf, /email, /help)

### 4. Specialized Business Intelligence Agents

#### Financial Agent (`src/agents/financial_agent.py`)
- Overdue payment tracking
- Price revision recommendations
- Revenue impact analysis
- Payment delay patterns

#### License Audit Agent (`src/agents/license_audit_agent.py`)
- Software usage compliance
- Unused license identification
- Cost optimization opportunities
- Anomalous access detection

#### Company Ticket Agent (`src/agents/company_specific_ticket_agent.py`)
- Customer satisfaction metrics
- Resolution time analysis
- Ticket category distribution
- Service quality benchmarking

#### MSP Insights Agent (`src/agents/msp_insights_agent.py`)
- Cross-domain analytics
- Profitability analysis
- Contract management
- Technician workload optimization

### 5. Real-time Dashboard (`Frontend/`)
- **Live ticket processing** visualization
- **Financial KPIs** and critical alerts
- **Interactive charts** for revenue prediction
- **Customer management** with detailed profiles
- **AI chatbot integration** for natural language queries

## 🛠️ Installation & Setup

### Prerequisites
- **Python 3.8+**
- **Node.js 16+**
- **SQLite 3**
- **Google Gemini API Key** (for AI features)

### Backend Setup

1. **Navigate to the Agents directory:**
   ```bash
   cd Agents/
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env file with your API keys:
   # GEMINI_API_KEY=your_gemini_api_key_here
   ```

5. **Initialize the database:**
   ```bash
   # The SQLite database will be created automatically on first run
   python main.py
   ```

6. **Start the FastAPI server:**
   ```bash
   python api.py
   # Server will run on http://localhost:8002
   ```

### Frontend Setup

1. **Navigate to the Frontend directory:**
   ```bash
   cd Frontend/
   ```

2. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

3. **Configure API endpoint:**
   ```bash
   # Edit src/config.js to match your backend URL
   export const API_BASE_URL = 'http://localhost:8002';
   ```

4. **Start the development server:**
   ```bash
   npm run dev
   # Frontend will run on http://localhost:5173
   ```

## 📊 Database Schema

The system uses SQLite with the following key tables:

- **companies** - Customer company profiles
- **tickets** - Support ticket records
- **payments** - Financial transaction history
- **technicians** - MSP staff information
- **customer_company_employees** - End-user profiles
- **software_inventory** - License management
- **company_contract** - Contract details

## 🔌 API Endpoints

### Core Ticket Management
- `POST /api/tickets/send` - Process next ticket
- `GET /api/tickets/timeline` - Get processing history
- `POST /api/tickets/approve` - Approve/reject tickets
- `WebSocket /ws/tickets` - Real-time updates

### Business Intelligence
- `GET /api/dashboard/metrics` - Key performance indicators
- `GET /api/dashboard/critical-alerts` - System alerts
- `GET /api/revenue-prediction` - Financial forecasting
- `POST /api/chatbot/respond` - AI assistant queries

### Client Management
- `GET /api/clients/allClients` - Customer list
- `GET /api/clients/{id}/tickets` - Customer tickets
- `GET /api/clients/{id}/softwares` - License assignments
- `GET /api/clients/{id}/billing-summary` - Financial overview

### Agent Services
- `POST /api/agent/people/suggest` - Contact recommendations
- `POST /api/agent/software/recommend` - Software suggestions
- `POST /api/agent/upload` - Document analysis
- `GET /api/price-revision/{id}` - Pricing recommendations

### File Operations
- `GET /api/download/{filename}` - Export downloads
- `GET /api/files/list` - Available reports
- `DELETE /api/files/{filename}` - File cleanup

## 🤖 AI Agent Commands

The system supports natural language queries and slash commands:

### Slash Commands
- `/pdf [query]` - Generate PDF report
- `/email-overdue` - Send payment reminders
- `/email-expiring` - License expiration notices
- `/help` - Command reference

### Natural Language Examples
- "Show me all overdue payments"
- "Which customers have the lowest satisfaction scores?"
- "Calculate potential savings from unused licenses"
- "What's our total revenue this month?"
- "Find companies with high ticket volumes"

## 🔄 System Workflow

### Ticket Processing Flow
1. **Ticket Ingestion** - Load from JSON or API
2. **SLA Validation** - AI-powered compliance check
3. **RAG Processing** - Knowledge base search
4. **Human Approval** - Queue for review
5. **Auto-Assignment** - Route to technicians
6. **Real-time Updates** - WebSocket notifications

### Business Intelligence Flow
1. **Query Analysis** - Understand user intent
2. **Agent Selection** - Route to specialized agents
3. **Parallel Execution** - Fetch data simultaneously
4. **Response Synthesis** - Combine insights
5. **Export Generation** - PDF/Excel reports

## 🔧 Configuration

### Environment Variables (.env)
```bash
# AI Services
GEMINI_API_KEY=your_gemini_api_key

# Database
DATABASE_PATH=./databases/msp_data.db

# File Storage
UPLOADS_FOLDER=./uploads
EXPORTS_FOLDER=./exports

# API Configuration
API_HOST=0.0.0.0
API_PORT=8002
```

### Frontend Configuration (src/config.js)
```javascript
export const API_BASE_URL = 'http://localhost:8002';
export const WS_BASE_URL = 'ws://localhost:8002';
```

## 📈 Performance & Scalability

- **Concurrent Processing** - Multi-threaded agent execution
- **WebSocket Optimization** - Efficient real-time updates
- **Database Indexing** - Optimized query performance
- **Caching Strategy** - Vector embeddings and model results
- **Rate Limiting** - API protection and quota management

## 🔒 Security Features

- **CORS Protection** - Cross-origin request filtering
- **Input Validation** - Pydantic model validation
- **File Type Restrictions** - PDF-only uploads
- **Path Traversal Protection** - Secure file operations
- **API Rate Limiting** - Abuse prevention

## 🧪 Testing & Development

### Running Tests
```bash
# Backend tests
cd Agents/
python -m pytest

# Frontend tests
cd Frontend/
npm test
```

### Development Mode
```bash
# Backend with auto-reload
uvicorn api:app --reload --host 0.0.0.0 --port 8002

# Frontend with hot reload
npm run dev
```

## 📝 Logging & Monitoring

- **Structured Logging** - JSON format with timestamps
- **WebSocket Monitoring** - Connection tracking
- **Agent Performance** - Execution time metrics
- **Error Tracking** - Comprehensive error handling
- **Database Monitoring** - Query performance logs

## 🚀 Deployment

### Production Deployment
```bash
# Backend
gunicorn api:app -w 4 -k uvicorn.workers.UvicornWorker

# Frontend
npm run build
# Serve dist/ folder with nginx or similar
```

### Docker Deployment
```bash
# Build containers
docker-compose up --build

# Scale services
docker-compose up --scale backend=3
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support & Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Ensure SQLite file permissions
   - Check database path in configuration

2. **AI API Rate Limits**
   - Verify Gemini API key
   - Monitor usage quotas

3. **WebSocket Connection Issues**
   - Check firewall settings
   - Verify CORS configuration

4. **File Upload Problems**
   - Ensure uploads directory exists
   - Check file size limits

### Getting Help
- Check the logs in `Agents/logs/`
- Review API documentation at `/docs`
- Submit issues on GitHub
- Contact support team

## 🔮 Future Roadmap

- **Multi-tenant Support** - Enterprise scaling
- **Advanced Analytics** - Machine learning insights
- **Mobile Application** - iOS/Android apps
- **Integration Hub** - Third-party connectors
- **Advanced Security** - OAuth2/SAML support
- **Performance Optimization** - Redis caching
- **Automated Testing** - CI/CD pipeline

---


This system represents a comprehensive solution for modern Managed Service Providers, combining the power of AI, real-time analytics, and intuitive user experience to deliver exceptional IT service management.
