# 🚀 Minori HRMS MCP Server

Enterprise-grade Model Context Protocol (MCP) server for HRMS analytics, KPI intelligence, workforce insights, and autonomous AI agents. Built with FastAPI, Cloudflare D1, and Groq LLM pipelines.

---

## 🗺️ System Architecture

This repository facilitates natural language querying over relational HRMS databases using a structured Text-to-SQL translation and verification pipeline.

```mermaid
graph TD
    classDef client fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef mcp fill:#ede7f6,stroke:#5e35b1,stroke-width:2px;
    classDef db fill:#fbe9e7,stroke:#d84315,stroke-width:2px;
    classDef security fill:#ffebee,stroke:#c62828,stroke-width:2px;

    User([User / AI Agent]) -->|Natural Language Query| Server[MCP Server: server.py]
    Server -->|Ask Database / Insights| Engine[Text-to-SQL Engine]

    subgraph "AI Query Pipeline"
        Engine -->|1. Check| FP{Fast Path Handler}
        FP -->|Match| FP_Exec[Execute Predefined SQL]
        FP -->|No Match| Cache{Query Cache}
        Cache -->|Hit| Cache_Return[Return Cached Response]
        Cache -->|Miss| TS[Table Selector]
        
        TS -->|Select Tables| SB[Schema Builder]
        SB -->|Build Prompt Context| PB[Prompt Builder]
        PB -->|System + User Prompts| LLM[LLM Service: Groq]
        LLM -->|Generated SQL| SV[SQL Validator]
        
        SV -->|Pass| Exec[Database Query Service]
        SV -->|DDL/DML Blocked| Block([Blocked Query Response])
    end

    Exec -->|Execute Query| D1[Cloudflare D1 Client]
    D1 -->|SQL Results| AG[Answer Generator]
    AG -->|Natural Language Answer| Engine
    
    FP_Exec --> Exec
    
    class User,Server client;
    class Engine,FP,Cache,TS,SB,PB,LLM,AG mcp;
    class Exec,D1 db;
    class SV,Block security;
```

### Data & Execution Flow
1. **Query Ingestion**: The client makes a call to one of the server's tools (e.g., `ask_database`, `hr_insights`, `hr_agent`).
2. **Fast-Path Check**: The `FastPathHandler` executes pattern matching for simple queries (e.g., "count employees") and runs predefined SQL, bypassing LLM translation.
3. **Query Cache**: If the query misses the fast path, the in-memory cache is checked for a matching question.
4. **Table & Schema Scoping**: The `TableSelector` evaluates semantic keywords to identify relevant tables, and the `SchemaBuilder` constructs a trimmed schema definition context for the prompt.
5. **Prompt Construction**: The `PromptBuilder` resolves terminology definitions from a `BusinessDictionary` (handling HR jargon like "FTR" or "rework") and formats instructions with few-shot SQL examples.
6. **SQL Generation**: The query is sent to the `LLMService` (using Groq) which generates the SQL command.
7. **SQL Guardrail Validation**: The `SQLValidator` evaluates the query structure and blocks mutations (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, etc.) to guarantee read-only operations.
8. **D1 Execution**: The read-only query is run by the `D1Client` database service.
9. **NL Response Formulator**: The `AnswerGenerator` converts the SQL records back into a coherent, structured markdown summary returned to the client.

---

## 📂 Project Directory Structure

```
minori-hrms-mcp/
├── data/                       # Dataset imports and seed templates
│   ├── imports/                # Target folder for runtime timesheet imports
│   └── seed/                   # Pre-defined mock CSV and Excel database records
├── docs/                       # System design and documentation directories (API, Security, Data-model)
├── infra/                      # Infrastructure scripts (Cloudflare configs, Docker configuration)
├── logs/                       # Application event and error logs
├── scripts/                    # Helper scripts for system diagnostics and loading data
├── src/                        # Main source directory
│   ├── agent/                  # Multi-turn autonomous agent & session memory
│   │   ├── conversation_memory.py  # In-memory sliding history manager
│   │   └── hr_agent.py             # LangChain/LangGraph ReAct agent loop
│   ├── api/                    # FastAPI application, OpenAPI endpoints
│   │   ├── routes/             # REST resource endpoints (e.g., employees.py)
│   │   └── app.py              # Application runner and middleware setup
│   ├── core/                   # Shared configurations, logging and exception classes
│   ├── database/               # Relational D1 client connections & repositories
│   │   ├── migrations/         # SQL schema migration files (001-007)
│   │   └── d1_client.py        # Cloudflare D1 integration client
│   ├── mcp_server/             # Model Context Protocol registration and server startup
│   │   └── server.py           # MCP server main module registering FastMCP tools
│   ├── schemas/                # Request & response validation models
│   └── services/               # Internal backend business logic
│       ├── ai/                 # Text-to-SQL pipeline services (cache, validators, LLM)
│       ├── analytics/          # Department metrics, utilization, rework statistics
│       └── sync/               # Excel and CSV sync data parsers
└── tests/                      # Verification suite
    ├── unit/                   # Modular unit tests (pytest)
    ├── benchmark_queries.json  # Comprehensive SQL/Answer evaluation test cases
    └── run_benchmarks.py       # Pipeline execution benchmark harness
```

---

## ⚡ Core Features

- **Model Context Protocol (MCP)**: Exposes database operations, timesheet loaders, and natural language analytics as interoperable tools.
- **Robust Text-to-SQL Translation**: Multi-stage pipeline featuring schema scoping, validation, and Groq-powered natural language answers.
- **SQL Validation Guardrails**: Restricts DDL/DML mutation keywords (`DROP`, `DELETE`, `UPDATE`, `ALTER`, etc.) to enforce read-only execution.
- **High-Performance Query Cache**: In-memory caching layer to speed up identical questions and optimize token consumption.
- **Fast-Path Pattern Matching**: Bypasses LLM generation for standard administration queries (e.g., table lists, employee counts, department listings).
- **FastAPI Web Endpoints**: REST API layer for programmatic employee operations and Swagger documentation.
- **Autonomous Multi-Turn Agent**: LangChain/LangGraph powered HR agent capable of performing complex multi-step analysis while maintaining session history.

---

## 🗄️ Database Schema & Data Model

The server queries a relational Cloudflare D1/SQLite schema comprising the following core tables:

### 1. `employees`
Stores employee profiles and core organization variables:
- `employee_id` (TEXT, Primary Key): Unique identifier (e.g., `EMP0001`).
- `first_name` & `last_name` (TEXT)
- `email` (TEXT, Unique)
- `department` & `job_title` (TEXT): Team classification and role descriptor.
- `employment_type` (TEXT): Classification (e.g., `FULL_TIME`, `CONTRACTOR`).
- `date_of_joining` (TEXT): ISO date string.
- `annual_salary_inr` (INTEGER): Annual pay in Indian Rupees.
- `manager_id` (TEXT): Self-referential employee ID link.
- `status` (TEXT): Account status (e.g., `ACTIVE`, `INACTIVE`).

### 2. `timesheets`
Frictional log of individual tasks completed by workers:
- `employee_id` (TEXT) & `employee_name` (TEXT)
- `task_name` & `task_status` (TEXT)
- `eta_hours` (REAL): Estimated completion time.
- `actual_hours` (REAL): Logged completion time.
- `ftr_flag` (INTEGER, `0` or `1`): **First Time Right** flag. A value of `1` indicates no rework was needed.
- `rework_flag` (INTEGER, `0` or `1`): Rework flag. A value of `1` indicates the task required corrective action.
- `completion_date` (TEXT)
- `month` (INTEGER) & `year` (INTEGER)

### 3. `timesheet_summary`
Aggregated monthly metrics for team analysis:
- `employee_name` (TEXT) & `role` (TEXT)
- `month` (TEXT)
- `total_tasks` (INTEGER) & `total_hours` (REAL)
- `rework_tasks` (INTEGER)
- `utilization_percentage` (REAL): Portion of time spent on billable activities.

### 4. `task_logs`
Historical project task listings with estimation metadata:
- `employee_name` & `role` (TEXT)
- `task_description` (TEXT)
- `actual_hours` (REAL)
- `eta` (TEXT)
- `confidence` (TEXT): Dev confidence rating.

---

## 🛠️ Getting Started

### 1. Prerequisites & Environment Setup

Configure the development environment using Python 3.12 (or newer):

```bash
# 1. Create a virtual environment
python -m venv venv

# 2. Activate the virtual environment
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Windows CMD:
.\venv\Scripts\activate.bat
# On macOS/Linux:
source venv/bin/activate

# 3. Install required dependencies
pip install -r requirements.txt
pip install pytest
```

### 2. Configuration

Copy the `.env.example` file to `.env` and populate your credentials:

```bash
cp .env.example .env
```

Ensure the following variables are configured in `.env`:
*   `D1_DATABASE_ID`: Cloudflare D1 database ID.
*   `D1_API_TOKEN`: Cloudflare client API token.
*   `D1_ACCOUNT_ID`: Cloudflare Account ID.
*   `GROQ_API_KEY`: API Key for Groq Cloud.
*   `DEBUG_MODE`: Set to `True` to enable raw SQL output in responses.

---

## 📋 Running the Application & MCP Tools

### 1. Running the MCP Server
Launch the MCP server directly using Python:
```bash
python -m src.mcp_server.server
```

### 2. Testing with MCP Inspector
Inspect the server capabilities and interact with exposed tools using the browser-based `@modelcontextprotocol/inspector`:
```bash
# On Windows (utilizing the venv python executable):
npx -y @modelcontextprotocol/inspector venv/Scripts/python -m src.mcp_server.server

# On macOS/Linux:
npx -y @modelcontextprotocol/inspector venv/bin/python -m src.mcp_server.server
```
Once loaded, you can test these tools:
*   `list_tables`: Enumerate all tables in the schema.
*   `describe_table`: Fetch schema details for a specific table.
*   `ask_database`: Query the database in natural language.
*   `hr_insights`: Get specialized analysis (e.g., top performers, rework rates).
*   `load_timesheets`: Import timesheet documents from `/data/imports/`.
*   `hr_agent`: Perform multi-turn, multi-source cognitive agent analysis.

### 3. FastAPI Web Server
Expose REST API endpoints for employee lookups and Swagger UI:
```bash
python -m uvicorn src.api.app:app --reload
```
Once started, open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) in your browser.

---

## 🧪 Testing & Validation

### 1. Run Unit Tests
Run the test suite using `pytest` inside the virtual environment:
```bash
# Run tests using the environment's python package
.\venv\Scripts\python -m pytest tests/unit
```

### 2. Run the Benchmark Suite
Evaluate Text-to-SQL translation adherence, Fast-Path triggers, cache performance, and validation security:
```bash
.\venv\Scripts\python -m tests.run_benchmarks
```
The reports are stored in `tests/benchmark_results/latest.json`.