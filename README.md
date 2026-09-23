# 🏏 Autonomous Text-to-SQL Agent with Self-Healing Loop

An enterprise-ready **Autonomous Text-to-SQL Agent** built with **LangChain**, **Groq LPU Inference**, **SQLite**, and **Streamlit**. 

This agent translates natural language questions into executable SQL queries against real-world cricket database records (IPL 2021–2024), automatically catches and **self-heals execution/syntax errors**, and evaluates execution accuracy against a golden benchmark.

---

## 🌟 Key Highlights

- **⚡ Blazing Fast LPU Inference:** Uses Groq Cloud LPUs with models like Qwen 27B for sub-second query generation and execution.
- **🔄 Autonomous Self-Healing Feedback Loop:** When a generated SQL fails execution on the database engine, the agent dynamically captures the SQLite error trace, constructs a targeted debugging prompt, and iteratively repairs the query (up to 3 retries).
- **📊 Value-Based Execution Accuracy Evaluator:** Includes an advanced evaluation suite (`evaluator.py`) testing execution accuracy against golden datasets with flexible column-count tolerance (Path A subset matching).
- **🖥️ Clean Interactive UI:** Streamlit-powered dashboard showing query generation latency (ms), retry counts, formatted SQL output, and interactive data tables.
- **🛡️ Secure & Modular:** Environment-variable isolation for API keys, modular database abstraction, and clean separation between agent orchestration and evaluation.

---

## 🏗️ Architecture & Workflow

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

## 📁 Project Structure

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

## 🚀 Quickstart Guide

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/autonomous-text-to-sql-agent.git
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

## 🧪 Benchmark & Evaluation Suite

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

## 💼 Resume Bullet Points

If you are featuring this project on your resume, LinkedIn, or portfolio:

> - **Autonomous Text-to-SQL Agent with Self-Healing Loop:** Engineered an intelligent Text-to-SQL pipeline using LangChain, Groq LPUs, and SQLite, delivering sub-100ms natural language queries over relational datasets.
> - **Self-Correction Architecture:** Designed an autonomous error-recovery feedback loop that captures database runtime exceptions and iteratively self-heals faulty SQL queries within 3 retries, boosting query execution success rates.
> - **Evaluation Framework:** Implemented an execution-accuracy evaluation suite comparing model outputs against golden datasets with flexible column-count value tolerance.
> - **Full-Stack Deployment:** Built an interactive Streamlit analytics dashboard monitoring query latency, retry counts, generated SQL syntax, and tabular data outputs.
