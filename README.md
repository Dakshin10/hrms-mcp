# 📊 HRMS Analytics MCP Server

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white&style=for-the-badge)](https://python.org)
[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-Supported-purple?logo=model-context-protocol&style=for-the-badge)](https://modelcontextprotocol.io)
[![Cloudflare D1](https://img.shields.io/badge/Cloudflare-D1-orange?logo=cloudflare&logoColor=white&style=for-the-badge)](https://cloudflare.com)
[![Groq](https://img.shields.io/badge/LLM-Groq%20Pipeline-red?logo=groq&logoColor=white&style=for-the-badge)](https://groq.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

An enterprise-grade **Model Context Protocol (MCP) server** for HRMS analytics, workforce intelligence, and autonomous HR agents. Built on top of a relational database engine (Cloudflare D1/SQLite) and powered by high-performance LLM Text-to-SQL translation pipelines (Groq).

This platform acts as an intelligent bridge, allowing any MCP client (such as Claude Desktop, Cursor, or autonomous AI agents) to explore database schemas, perform analytics, sync with third-party tools like Google Sheets, and coordinate multi-step research through memory-enabled agentic routines.

---

## 🗺️ System Architecture

The server translates natural language queries into safe, optimized SQL execution plans through a validated multi-stage query pipeline.

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

1. **Query Ingestion**: The client invokes an analytical tool (e.g., `ask_database`, `hr_insights`, `hr_agent`).
2. **Fast-Path Evaluation**: The `FastPathHandler` matches routine query patterns (e.g., simple counts, aggregations) to run pre-compiled SQL, bypassing LLM processing.
3. **Query Caching**: A memory cache checks if a identical request has been processed recently.
4. **Context Isolation**: The `TableSelector` performs keyphrase mapping to isolate relevant tables, and `SchemaBuilder` compiles a minimal, token-efficient schema context.
5. **Prompt Synthesis**: The `PromptBuilder` resolves project-specific terms from a `BusinessDictionary` (e.g., interpreting definitions like "FTR" or "rework") and binds few-shot SQL examples.
6. **SQL Generation**: The LLM engine (Groq) generates standard SQL based on contextual rules.
7. **Security Guardrails**: The `SQLValidator` parses the SQL statement and blocks any mutating keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, etc.) to enforce read-only operations.
8. **Execution**: The query is executed safely against Cloudflare D1/SQLite.
9. **NL Response Formulator**: The `AnswerGenerator` packages raw record payloads into clean, semantic markdown tables and narratives.

---

## 📂 Project Directory Structure

```text
analytics-mcp/
├── data/                       # Datasets, imports, and database seeds
│   ├── imports/                # Runtime target folder for CSV/Excel timesheet imports
│   └── seed/                   # Pre-defined mock database records
├── docs/                       # Architecture diagrams and system design files
├── infra/                      # Cloudflare configurations and infrastructure files
├── logs/                       # Application runtime logs
├── scripts/                    # Command-line diagnostics and system helpers
├── src/                        # Primary source directory
│   ├── agent/                  # Autonomous ReAct agent and conversation memory
│   │   ├── conversation_memory.py  # Sliding conversation context window
│   │   ├── hr_agent.py             # LangChain/LangGraph agent routine
│   │   └── run_agent.py            # Local agent execution harness
│   ├── core/                   # Configurations, global exceptions, and logs
│   ├── mcp_server/             # Model Context Protocol registration and runner
│   │   └── server.py           # Core MCP server launcher
│   ├── schemas/                # Data verification and request validation schemas
│   ├── services/               # Underlying business logic
│   │   ├── ai/                 # Text-to-SQL logic, validator, cache, and LLM
│   │   ├── analytics/          # HR KPIs, employee utilization, rework, and FTR rates
│   │   └── database/           # D1 client connection pool and repository services
│   └── tools/                  # FastMCP modular tool declarations
│       ├── db_tools.py         # Schema inspections, raw SQL, and cache management
│       ├── employee_tools.py   # Roster lookup and search utilities
│       ├── hr_tools.py         # Advanced analytical routing and agent tools
│       ├── sheet_tools.py      # Google Sheets connection and fetching layers
│       └── timesheet_tools.py  # Local CSV/Excel data loaders
└── tests/                      # Testing & benchmarking suites
    ├── unit/                   # Unit test suite (pytest)
    ├── benchmark_queries.json  # Reference queries and validation metrics
    └── run_benchmarks.py       # Query translation evaluation runner
```

---

## 🗜️ Exposed MCP Tools

The server exposes **15 highly specialized tools** categorized below:

### 1. Database Exploration & SQL Tools
| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `list_tables` | *None* | List all relational tables present in the database. |
| `describe_table` | `table_name: str` | Retrieve the columns, data types, and keys for a specific table. |
| `execute_sql` | `sql: str` | Execute arbitrary SQL queries safely (strictly read-only). |
| `ask_database` | `question: str` | Solve natural language questions using automated Text-to-SQL. |
| `cache_stats` | *None* | Retrieve hit rates and occupancy statistics of the SQL translation cache. |

### 2. Employee Lookup Tools
| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `get_all_employees` | *None* | Fetch the complete employee roster. |
| `get_employee_by_id` | `employee_id: str` | Find detailed data for a specific employee profile. |
| `get_employees_by_department` | `department: str` | List employees belonging to a specific department. |
| `search_employees` | `keyword: str` | Perform a fuzzy text search across names, titles, departments, or emails. |

### 3. HR Analytical & Agentic Tools
| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `hr_insights` | `question: str` | Run analytical queries focusing on core KPIs like utilization, FTR, and rework. |
| `hr_agent` | `question: str`, `session_id: str` | Run a multi-turn analytical loop using persistent conversational memory. |
| `clear_session` | `session_id: str` | Clear history context for a given session. |

### 4. Data Integration & Loaders
| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `connect_google_sheet` | `sheet_url: str` | Authenticate and link a live Google Spreadsheet. |
| `fetch_sheet_data` | `sheet_url: str`, `worksheet_name: str` | Fetch rows directly from a specific worksheet. |
| `load_timesheets` | `file_path: str` | Parse local CSV or Excel sheets and insert data into the database. |

---

## 🗄️ Database Schema & Data Model

The D1 database features an optimized, relational schema mapping key HR variables:

### 1. `employees`
Contains identity, structure, and compensation metrics.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `employee_id` | `TEXT` | Primary Key | Unique ID (e.g., `EMP0001`) |
| `first_name` | `TEXT` | Not Null | Given name |
| `last_name` | `TEXT` | Not Null | Family name |
| `email` | `TEXT` | Unique | Employee email |
| `department` | `TEXT` | - | Assigned department |
| `job_title` | `TEXT` | - | Current role |
| `employment_type`| `TEXT` | - | E.g., `FULL_TIME`, `CONTRACTOR` |
| `date_of_joining`| `TEXT` | - | ISO Joining Date (`YYYY-MM-DD`) |
| `annual_salary_inr`| `INTEGER` | - | Salary in INR |
| `manager_id` | `TEXT` | - | Self-referencing link to supervisor's `employee_id` |
| `status` | `TEXT` | - | Account state (e.g., `ACTIVE`, `INACTIVE`) |

### 2. `timesheets`
Granular log records detailing discrete developer and operations tasks.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `employee_id` | `TEXT` | Foreign Key | Links to `employees.employee_id` |
| `employee_name` | `TEXT` | - | Redundant display name |
| `task_name` | `TEXT` | - | Name of task |
| `task_status` | `TEXT` | - | E.g., `COMPLETED`, `IN_PROGRESS` |
| `eta_hours` | `REAL` | - | Estimated hours required |
| `actual_hours` | `REAL` | - | Actual hours spent |
| `ftr_flag` | `INTEGER` | `0` or `1` | First Time Right flag (1 = no rework, 0 = rework) |
| `rework_flag` | `INTEGER` | `0` or `1` | Rework flag (1 = task required rework) |
| `completion_date`| `TEXT` | - | ISO Completion Date |
| `month` | `INTEGER` | - | Numeric month (1-12) |
| `year` | `INTEGER` | - | Calendar year |

### 3. `timesheet_summary`
Monthly aggregated statistics on performance, productivity, and utilization.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `employee_name` | `TEXT` | - | Employee name |
| `role` | `TEXT` | - | Job role |
| `month` | `TEXT` | - | Text month (e.g., `January`) |
| `total_tasks` | `INTEGER` | - | Count of total logged tasks |
| `total_hours` | `REAL` | - | Cumulative actual hours |
| `rework_tasks` | `INTEGER` | - | Count of tasks requiring rework |
| `utilization_percentage` | `REAL` | - | Percentage of working hours spent on tasks |

### 4. `task_logs`
Historical project task logs and estimation confidence data.
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `employee_name` | `TEXT` | - | Worker name |
| `role` | `TEXT` | - | Worker role |
| `task_description`| `TEXT` | - | Full task description text |
| `actual_hours` | `REAL` | - | Hours spent on task |
| `eta` | `TEXT` | - | Projected deadline text or category |
| `confidence` | `TEXT` | - | Developer confidence indicator |

---

## 🛠️ Getting Started

### 1. Installation & Environment Setup

Configure the development environment using Python 3.12+:

```bash
# 1. Create a virtual environment
python -m venv venv

# 2. Activate the environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (CMD):
.\venv\Scripts\activate.bat
# On macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install pytest
```

### 2. Environment Variables

Create a configuration file in the project root:

```bash
cp .env.example .env
```

Define the following environment variables inside `.env`:

```env
D1_DATABASE_ID=your_cloudflare_d1_database_id
D1_API_TOKEN=your_cloudflare_d1_api_token
D1_ACCOUNT_ID=your_cloudflare_d1_account_id
GROQ_API_KEY=your_groq_api_key
DEBUG_MODE=False
```

---

## 📋 Running the MCP Server

The server supports two distinct communication protocols. Choose the transport method matching your client interface:

### Option A: Standard Stdio Transport (Default)
Best for local application clients (e.g., Claude Desktop, Cursor) communicating directly over system standard input and output streams.

```bash
python -m src.mcp_server.server
```

### Option B: Server-Sent Events (SSE) Transport
Enables the server to run as a network API, exposing HTTP routes for remote clients to receive real-time streams and post requests.

```bash
# On Windows (PowerShell):
$env:MCP_TRANSPORT="sse"
$env:MCP_PORT="8000"
$env:MCP_HOST="0.0.0.0"
python -m src.mcp_server.server

# On Windows (CMD):
set MCP_TRANSPORT=sse
set MCP_PORT=8000
set MCP_HOST=0.0.0.0
python -m src.mcp_server.server

# On macOS/Linux:
MCP_TRANSPORT=sse MCP_PORT=8000 MCP_HOST=0.0.0.0 python -m src.mcp_server.server
```

*When active, clients can establish streams at `http://localhost:8000/sse` and POST message objects to `http://localhost:8000/message`.*

---

## 🔍 Testing with MCP Inspector

Test and inspect tool definitions interactively using the official `@modelcontextprotocol/inspector` web interface:

```bash
# On Windows:
npx -y @modelcontextprotocol/inspector venv/Scripts/python -m src.mcp_server.server

# On macOS/Linux:
npx -y @modelcontextprotocol/inspector venv/bin/python -m src.mcp_server.server
```

Open the local URL displayed in your console to verify, inspect, and trigger the 15 available server tools.

---

## 🔌 Claude Desktop Configuration

Configure Claude Desktop to link this server dynamically. Modify your local configuration file (located at `%APPDATA%\Claude\claude_desktop_config.json` on Windows, or `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "hrms-analytics-mcp": {
      "command": "C:/path/to/hrms-analytics-mcp/venv/Scripts/python",
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

> [!IMPORTANT]
> - Replace `C:/path/to/hrms-analytics-mcp` with your project's absolute directory path.
> - Always use forward slashes (`/`) even on Windows platforms inside the JSON configuration.
> - Replace all credential variables with your real Cloudflare and Groq credentials.

---

## 📊 Google Sheets Integration

The Analytics MCP server provides secure, authenticated connections to Google Sheets APIs. Credentials and authorization keys remain entirely server-side.

### 1. Credentials Configuration
To activate Google Sheets tools, retrieve your Google Cloud Desktop Client credential configuration JSON and place it exactly at:
```text
credentials/client_secret.json
```
> [!NOTE]
> The `credentials/` folder is pre-registered in `.gitignore` to prevent committing sensitive keys to remote repositories.

### 2. Authorization Handshake
When first calling any Google Sheets tool:
1. The server starts a local OAuth2 authorization routine.
2. Your system will open a browser window requesting account permissions.
3. Upon approval, the server creates `credentials/token.json` locally to store the authentication tokens.
4. Subsequent requests refresh this token in the background automatically.

### 3. Integrated Tools
*   `connect_google_sheet(sheet_url: str)`: Link a Google Sheet. Resolves connection status and worksheet structures.
*   `fetch_sheet_data(sheet_url: str, worksheet_name: str)`: Read rows from a specific worksheet directly into the active context.

### 4. Security Enforcement
*   **Decoupled Frontend**: Clients interact strictly with the MCP protocol; they never communicate directly with Google's API endpoints.
*   **Git Protection**: Wildcard rules in `.gitignore` block credentials or generated auth tokens from leaking.

---

## 🧪 Testing & Validation

### 1. Run Unit Tests
Validate functional structures and classes via `pytest`:

```bash
venv/Scripts/python -m pytest tests/unit
```

### 2. Run Benchmarks
Evaluate translation accuracy and pipeline timing stats:

```bash
venv/Scripts/python -m tests.run_benchmarks
```
*Comprehensive results are exported to `tests/benchmark_results/latest.json`.*