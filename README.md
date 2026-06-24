# 🚀 Minori HRMS Analytics MCP Server

Enterprise-grade **Model Context Protocol (MCP) server** for HRMS analytics, KPI intelligence, workforce insights, and autonomous AI agents. Built with Python, Cloudflare D1, and Groq LLM pipelines.

This repository is a pure MCP server platform that exposes all analytics, database exploration, synchronization, and autonomous agents exclusively as interoperable MCP tools.

---

## 🗺️ System Architecture

This repository facilitates natural language querying over relational HRMS databases using a structured Text-to-SQL translation and verification pipeline.

```mermaid
graph TD
    classDef client fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef mcp fill:#ede7f6,stroke:#5e35b1,stroke-width:2px;
    classDef db fill:#fbe9e7,stroke:#d84315,stroke-width:2px;
    classDef security fill:#ffebee,stroke:#c62828,stroke-width:2px;

    User([User / AI Agent]) -->|MCP Tool Request| Server[MCP Server: server.py]
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
1. **Query Ingestion**: The client calls one of the server's tools (e.g., `ask_database`, `hr_insights`, `hr_agent`).
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
analytics-mcp/
├── data/                       # Dataset imports and seed templates
│   ├── imports/                # Target folder for runtime timesheet imports
│   └── seed/                   # Pre-defined mock CSV and Excel database records
├── docs/                       # System design and documentation directories
├── infra/                      # Infrastructure scripts (Cloudflare configs, Docker)
├── logs/                       # Application event and error logs
├── scripts/                    # Helper scripts for system diagnostics
├── src/                        # Main source directory
│   ├── agent/                  # Multi-turn autonomous agent & session memory
│   │   ├── conversation_memory.py  # In-memory sliding history manager
│   │   ├── hr_agent.py             # LangChain/LangGraph ReAct agent loop
│   │   └── run_agent.py            # Local agent runner
│   ├── core/                   # Shared configurations, logging and exceptions
│   ├── mcp_server/             # Model Context Protocol registration and runner
│   │   └── server.py           # Pure MCP server main runner
│   ├── schemas/                # Request & response validation models
│   ├── services/               # Internal backend business logic
│   │   ├── ai/                 # Text-to-SQL pipelines (cache, validators, LLM, text_to_sql)
│   │   ├── analytics/          # Department metrics, utilization, rework statistics
│   │   └── database/           # Relational D1 client connections, repositories & helpers
│   └── tools/                  # FastMCP modular tool implementation directory
│       ├── db_tools.py         # Table, sql execution, schema, and cache tools
│       ├── employee_tools.py   # Employee management tools
│       ├── hr_tools.py         # HR insights, HR agent, and session clearing tools
│       ├── sheet_tools.py      # Google Sheets connection and fetching tools
│       └── timesheet_tools.py  # Excel and CSV timesheet loading tools
└── tests/                      # Verification suite
    ├── unit/                   # Modular unit tests (pytest)
    ├── benchmark_queries.json  # Comprehensive SQL/Answer evaluation test cases
    └── run_benchmarks.py       # Pipeline execution benchmark harness
```

---

## 🗜️ Exposed MCP Tools

The server registers **15 specialized tools** available to any Model Context Protocol client:

### 1. Database Exploration & SQL Tools
*   `list_tables`: Enumerate all available tables.
*   `describe_table(table_name: str)`: Get schema definition (columns, types, keys) for a specific table.
*   `execute_sql(sql: str)`: Run read-only SQLite SELECT queries with schema-matching guardrails.
*   `ask_database(question: str)`: Translate natural language into optimized SQL, run it, and generate a text response.
*   `cache_stats`: Get current hit rate and counts for the query caching layer.

### 2. Employee Lookup Tools
*   `get_all_employees`: Retrieve full listings of all registered employees in the organization.
*   `get_employee_by_id(employee_id: str)`: Find detailed information for a specific worker by their employee ID (e.g. `EMP0001`).
*   `get_employees_by_department(department: str)`: Retrieve employee rosters belonging to a specified department.
*   `search_employees(keyword: str)`: Perform fuzzy matching on employees by name, email, department, or job title.

### 3. HR Analytical & Agentic Tools
*   `hr_insights(question: str)`: Route HR-specific queries (top performers, ETA delays, FTR rate, rework, utilization) to analytical services.
*   `hr_agent(question: str, session_id: str)`: Ask multi-step queries combining multiple analysis phases while retaining context memory.
*   `clear_session(session_id: str)`: Clear conversation history for a given session ID.

### 4. Data Integration & Loaders
*   `connect_google_sheet(sheet_url: str)`: Authenticate and link a live Google Spreadsheet URL or ID.
*   `fetch_sheet_data(sheet_url: str, worksheet_name: str)`: Fetch live rows from a specific worksheet.
*   `load_timesheets(file_path: str)`: Load timesheet exports (CSV/Excel) from the local directory into the relational database.

---

## 🗄️ Database Schema & Data Model

The server queries a relational Cloudflare D1/SQLite schema comprising the following core tables:

### 1. `employees`
Stores employee profiles and core organization variables:
*   `employee_id` (TEXT, Primary Key): Unique identifier (e.g., `EMP0001`).
*   `first_name` & `last_name` (TEXT)
*   `email` (TEXT, Unique)
*   `department` & `job_title` (TEXT): Team classification and role descriptor.
*   `employment_type` (TEXT): Classification (e.g., `FULL_TIME`, `CONTRACTOR`).
*   `date_of_joining` (TEXT): ISO date string.
*   `annual_salary_inr` (INTEGER): Annual pay in Indian Rupees.
*   `manager_id` (TEXT): Self-referential employee ID link.
*   `status` (TEXT): Account status (e.g., `ACTIVE`, `INACTIVE`).

### 2. `timesheets`
Frictional log of individual tasks completed by workers:
*   `employee_id` (TEXT) & `employee_name` (TEXT)
*   `task_name` & `task_status` (TEXT)
*   `eta_hours` (REAL): Estimated completion time.
*   `actual_hours` (REAL): Logged completion time.
*   `ftr_flag` (INTEGER, `0` or `1`): **First Time Right** flag. A value of `1` indicates no rework was needed.
*   `rework_flag` (INTEGER, `0` or `1`): Rework flag. A value of `1` indicates the task required corrective action.
*   `completion_date` (TEXT)
*   `month` (INTEGER) & `year` (INTEGER)

### 3. `timesheet_summary`
Aggregated monthly metrics for team analysis:
*   `employee_name` (TEXT) & `role` (TEXT)
*   `month` (TEXT)
*   `total_tasks` (INTEGER) & `total_hours` (REAL)
*   `rework_tasks` (INTEGER)
*   `utilization_percentage` (REAL): Portion of time spent on billable activities.

### 4. `task_logs`
Historical project task listings with estimation metadata:
*   `employee_name` & `role` (TEXT)
*   `task_description` (TEXT)
*   `actual_hours` (REAL)
*   `eta` (TEXT)
*   `confidence` (TEXT): Dev confidence rating.

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

## 📋 Running the MCP Server

The server can be launched in two different transport modes.

### Option A: Standard Stdio Transport (Default)
Suitable for local agent integrations (e.g. Claude Desktop, Cursor, local python clients) where the client communicates directly over standard input/output streams:

```bash
# Run over stdio (default)
python -m src.mcp_server.server
```

### Option B: Server-Sent Events (SSE) Transport
Suitable for remote deployment as a network-accessible service. The server runs as an HTTP server that streams events to clients:

```bash
# Set environment variables to run in SSE mode
# On Windows PowerShell:
$env:MCP_TRANSPORT="sse"
$env:MCP_PORT="8000"
$env:MCP_HOST="0.0.0.0"
python -m src.mcp_server.server

# On CMD:
set MCP_TRANSPORT=sse
set MCP_PORT=8000
set MCP_HOST=0.0.0.0
python -m src.mcp_server.server

# On macOS/Linux:
MCP_TRANSPORT=sse MCP_PORT=8000 MCP_HOST=0.0.0.0 python -m src.mcp_server.server
```

Once running, the client can connect to the Server-Sent Events endpoint at `http://localhost:8000/sse` and post messages to `http://localhost:8000/message`.

---

## 🔍 Testing with MCP Inspector

Inspect the server capabilities and interact with exposed tools using the browser-based `@modelcontextprotocol/inspector`:

```bash
# On Windows (utilizing the venv python executable):
npx -y @modelcontextprotocol/inspector venv/Scripts/python -m src.mcp_server.server

# On macOS/Linux:
npx -y @modelcontextprotocol/inspector venv/bin/python -m src.mcp_server.server
```

Once loaded in your browser, you can run any of the 15 registered tools to test schema reading, employee roster fetching, CSV timesheet loading, or NL SQL questioning.

---

## 🔌 Claude Desktop Configuration

To connect this MCP server to Claude Desktop, add the following to your `claude_desktop_config.json` (located at `%APPDATA%\Claude\claude_desktop_config.json` on Windows, or `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "minori-hrms-analytics": {
      "command": "C:/path/to/minori-hrms-mcp/venv/Scripts/python",
      "args": ["-m", "src.mcp_server.server"],
      "env": {
        "D1_DATABASE_ID": "your_d1_database_id",
        "D1_API_TOKEN": "your_d1_api_token",
        "D1_ACCOUNT_ID": "your_d1_account_id",
        "GROQ_API_KEY": "your_groq_api_key",
        "DEBUG_MODE": "False"
      }
    }
  }
}
```

> [!NOTE]
> Make sure to replace `C:/path/to/minori-hrms-mcp` with the absolute path to your repository, use forward slashes (`/`) even on Windows in the JSON configuration, and insert your actual API credentials.

---

## 📊 Google Sheets Integration

The Analytics MCP server supports secure integration with the Google Sheets API. All OAuth operations and credentials remain strictly server-side and are never exposed to any frontend dashboard.

### 1. Placement of Credentials
To enable the Google Sheets tools, you must download your OAuth 2.0 Desktop Client credentials from the Google Cloud Console and place them in the following directory:
```text
credentials/client_secret.json
```
*(This folder and its contents are automatically ignored by git via `.gitignore` to prevent secret exposure.)*

### 2. Authorization Flow
The first time a Google Sheets tool is invoked:
1. The server starts a local OAuth2 authorization flow.
2. A browser window will open asking you to authorize the application.
3. Once authorized, a `credentials/token.json` file is created automatically to store authentication tokens.
4. Subsequent requests refresh this token silently as needed.

### 3. Exposed Tools
*   `connect_google_sheet(sheet_url: str)`:
    - Verifies credentials and links a Google Sheet by its full URL or its 44-character ID.
    - Returns sheet information and worksheet lists.
*   `fetch_sheet_data(sheet_url: str, worksheet_name: str)`:
    - Fetches records from the specified worksheet within the sheet.

### 4. Security Considerations
- **No Direct Frontend Access**: The frontend dashboard communicates solely with the MCP server; it never accesses Google APIs directly.
- **Git Safety**: All files inside `credentials/` and all `.json` files (excluding `package.json` manifests) are blacklisted in `.gitignore`.

---

## 🧪 Testing & Validation

### 1. Run Unit Tests
Run the test suite using `pytest` inside the virtual environment:
```bash
# Run tests using the environment's python package
venv/Scripts/python -m pytest tests/unit
```

### 2. Run the Benchmark Suite
Evaluate Text-to-SQL translation adherence, Fast-Path triggers, cache performance, and validation security:
```bash
venv/Scripts/python -m tests.run_benchmarks
```
The reports are stored in `tests/benchmark_results/latest.json`.