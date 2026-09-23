# Autonomous Text-to-SQL Agent with Self-Healing Loop

An enterprise-ready **Autonomous Text-to-SQL Agent** built with **LangChain**, **Groq LPU Inference**, **SQLite**, and **Streamlit**. 

This agent translates natural language questions into executable SQL queries against real-world cricket database records (IPL 2021-2024), automatically catches and **self-heals execution/syntax errors**, and evaluates execution accuracy against a golden benchmark.

---

## Key Highlights

- **Blazing Fast LPU Inference:** Uses Groq Cloud LPUs with models like Qwen 27B for sub-second query generation and execution.
- **Autonomous Self-Healing Feedback Loop:** When a generated SQL fails execution on the database engine, the agent dynamically captures the SQLite error trace, constructs a targeted debugging prompt, and iteratively repairs the query (up to 3 retries).
- **Value-Based Execution Accuracy Evaluator:** Includes an advanced evaluation suite (`evaluator.py`) testing execution accuracy against golden datasets with flexible column-count tolerance (Path A subset matching).
- **Clean Interactive UI:** Streamlit-powered dashboard showing query generation latency (ms), retry counts, formatted SQL output, and interactive data tables.
- **Secure & Modular:** Environment-variable isolation for API keys, modular database abstraction, and clean separation between agent orchestration and evaluation.

---

## Architecture & Workflow

```text
User Question (Plain English)
             │
             ▼
   [ Streamlit UI / app.py ]
             │
             ▼
  [ Schema Extraction + Context ]
             │
             ▼
    [ LangChain + ChatGroq ] ───► Generates SQL Query
             │
             ▼
     [ SQLite Database ] ──────── (Execute SQL)
             │
       ┌─────┴────────────────┐
       │                      │
   [ Success ]            [ Syntax/Schema Error ]
       │                      │
       │                      ▼
       │             Feed Error back to LLM
       │             (Self-Healing Loop - Retries: 1..3)
       │                      │
       │                      └───────► (Re-evaluate)
       ▼
 Display Execution Latency,
 Formatted SQL, and Tabular Results
```

---

## Project Structure

```text
├── app.py                      # Interactive Streamlit Web UI
├── main.py                     # Core agent logic & self-healing loop
├── evaluator.py                # Value-based execution accuracy comparison
├── models.py                   # Configured AI models on Groq
├── db.py                       # Database connection and helper utilities
├── schema.sql                  # Database schema definitions
├── golden_dataset.csv          # Benchmark dataset for evaluation
├── requirements.txt            # Python dependencies
├── .env.example                # Sample environment configuration
└── ipl_2021_2024.db            # SQLite database (matches, deliveries, players)
```

---

## Quickstart Guide

### 1. Clone the Repository
```bash
git clone https://github.com/codingsexpert/autonomous-text-to-sql-agent.git
cd autonomous-text-to-sql-agent
```

### 2. Set Up Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and insert your free API key from [Groq Console](https://console.groq.com/keys):
```bash
cp .env.example .env
```
Inside `.env`:
```env
GROQ_API_KEY=gsk_your_actual_api_key_here
```

### 5. Launch the Streamlit App
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## Benchmark & Evaluation Suite

To run automated evaluations across the golden benchmark dataset:
```bash
python main.py
```
This will:
1. Load questions and verified ground-truth SQL from `golden_dataset.csv`.
2. Generate SQL using the configured LLMs.
3. Compare the executed output with ground-truth values via `evaluator.py`.
4. Export detailed execution accuracy metrics to `eval_results.csv`.

---

## System Architecture & Scalability Optimizations ⚡
This project is built mimicking **Production-Grade Data Engineering Systems**. It includes several advanced optimization strategies for latency reduction and LLM safety:

### 1. In-Memory Exact Match Caching
Eliminates LLM latency for repeated analytical queries. If a question exists in `query_cache.json`, the SQL is fetched and executed instantly in `0.0ms` (LLM bypassed).

### 2. Query Performance Optimizer (AI DBA)
Features an **Actor-Critic (Multi-Agent) Pattern**. A secondary LLM pass acts as a Senior Database Administrator to evaluate the execution plan of generated queries, exposing bottlenecks (e.g. redundant subqueries) and recommending index creation.

### 3. Query Security Guardrails
Text-to-SQL agents are vulnerable to prompt-injection that can execute destructive commands. This agent implements strict application-level guardrails that block `DROP`, `DELETE`, `UPDATE`, `INSERT`, and `ALTER` operations before execution, maintaining a strict Read-Only environment.

### 4. Smart Chart Render Engine
Implements a dynamic rendering engine that infers SQLite Object output types, coerces datatypes, and automatically generates **Plotly Donut/Bar/Area Charts** optimized with Viridis and Pastel themes based on categorical volume.
