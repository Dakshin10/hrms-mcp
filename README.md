# minori-hrms-mcp

Enterprise-grade MCP server for HRMS analytics, KPI intelligence, workforce insights, and AI agents.

## Architecture

```
HRMS
 ↓
Sync Service
 ↓
Cloudflare D1
 ↓
Repository Layer
 ↓
MCP Server
 ↓
AI Agents
```

## Getting Started

### 1. Prerequisites & Environment Setup
To set up the development environment:

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
Copy the `.env.example` file to `.env` and fill in the required parameters (Cloudflare D1 credentials and Groq API Key):
```bash
cp .env.example .env
```

Ensure the following variables are configured in `.env`:
* `D1_DATABASE_ID`
* `D1_API_TOKEN`
* `D1_ACCOUNT_ID`
* `GROQ_API_KEY`

---

## How to Run Tests

### 1. Run Unit Tests
To run the complete suite of unit tests, execute the following command from the root directory:
```bash
# Run pytest explicitly on the unit tests folder
python -m pytest tests/unit
```

### 2. Run the Benchmark Suite
The project contains an evaluation/benchmark suite that tests natural language queries against expected SQL/answers, checks fast-path hit rates, and validates query caching:
```bash
# Execute the benchmark suite
python -m tests.run_benchmarks
```
Benchmark reports will be generated and saved to `tests/benchmark_results/latest.json`.

---

## Running the MCP Server
```bash
npx -y @modelcontextprotocol/inspector venv/Scripts/python src/mcp_server/server.py
```


> [!NOTE]
> Always run the python scripts as modules using the `-m` flag (or with `PYTHONPATH` set to the root directory) to ensure Python resolves the `src` packages correctly.

To start the MCP server locally using Python:
```bash
python -m src.mcp_server.server
```

### Testing the MCP Server with Inspector
You can inspect the MCP server capabilities and test the exposed tools using the `@modelcontextprotocol/inspector` tool:
```bash
npx -y @modelcontextprotocol/inspector venv/Scripts/python -m src.mcp_server.server
```
This launches a browser-based user interface where you can trigger tools like `list_tables`, `describe_table`, `hr_insights`, and `ask_database` interactively.

---

## Running the FastAPI Application

The project also includes a FastAPI application that exposes REST API endpoints for employee operations (e.g., `/employees`, `/employees/search/{keyword}`).

To start the FastAPI web server, run:
```bash
python -m uvicorn src.api.app:app --reload
```
Once started, the API will be available at `http://127.0.0.1:8000`. You can access the interactive Swagger documentation at `http://127.0.0.1:8000/docs`.