"""
main.py - controls the entire eval flow (ChatOpenRouter version).

For each model:
  1. load the model (via OpenRouter, through ChatOpenRouter)
  2. run the golden dataset (generate SQL for each question)
  3. run the generated SQL on the DB (get a result)
  4. evaluate (compare to gold, using evaluator.py)
  5. log the score

Files it depends on:
  - schema.sql             (the schema, for the prompt)
  - golden_dataset.csv     (questions + gold_sql + order_sensitive)
  - model_openrouter_slug.py  (the 5 models under test -> MODELS)
  - evaluator.py           (the comparison logic)

Setup:
  pip install langchain-openrouter python-dotenv pandas
  .env file with:  OPENROUTER_API_KEY=sk-or-...
"""

import os
import re
import json
import sqlite3
import pandas as pd
from dotenv import load_dotenv
import tempfile
from groq import Groq

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import time

from models import MODELS
from evaluator import evaluate_one

# ---------- CONFIG ----------
load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=API_KEY)

def transcribe_audio(audio_bytes):
    """Takes audio bytes, saves to a temp file, and transcribes using Groq Whisper."""
    if not audio_bytes:
        return ""
        
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file_path = tmp_file.name
            
        with open(tmp_file_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=(tmp_file_path, f.read()),
                model="whisper-large-v3",
                response_format="json",
                language="en"
            )
            
        os.remove(tmp_file_path)
        return transcription.text
    except Exception as e:
        print(f"Audio transcription error: {e}")
        return ""
DB_PATH = "ipl_2021_2024.db"
SCHEMA_PATH = "schema.sql"
GOLDEN_PATH = "golden_dataset.csv"
RESULTS_PATH = "eval_results.csv"
# ----------------------------


# ---------- helpers ----------
def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return f.read().strip()


def load_golden():
    return pd.read_csv(GOLDEN_PATH)


def make_llm(slug):
    """Create a ChatGroq model for one Groq slug."""
    return ChatGroq(
        model_name=slug,
        groq_api_key=API_KEY,
        temperature=0,
        max_tokens=800,
    )


def clean_sql(raw):
    """Strip markdown fences / prose, return runnable SQL."""
    if not raw:
        return ""
    text = raw.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    text = re.sub(r"^\s*sql\s*\n", "", text, flags=re.IGNORECASE)
    m = re.search(r"\b(SELECT|WITH)\b", text, re.IGNORECASE)
    if m:
        text = text[m.start():]
    return text.strip().strip("`").rstrip(";").strip("`").strip()


CACHE_FILE = "query_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache_data):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache_data, f, indent=4)

def generate_and_heal_sql(question, schema, llm, conn, max_retries=3, chat_history=None):
    """
    Generates SQL, executes it, and self-heals if there are SQL errors.
    Returns (final_sql, df, retries_used, exec_time_ms, final_error, is_cached)
    """
    # 1. Check Exact Match Cache (0ms Latency)
    cache = load_cache()
    q_key = question.strip().lower()
    
    if q_key in cache:
        cached_sql = cache[q_key]
        df, err, t_ms = run_sql(conn, cached_sql)
        if err is None:
            # Cache Hit Success
            return cached_sql, df, 0, t_ms, None, True
            
    # Cache Miss - Generate using LLM
    system_msg = SystemMessage(content=(
        "You are an expert text-to-SQL generator. Given a database schema and a question, "
        "return a single SQL query that answers it. Use SQLite syntax. "
        "Return only the SQL query. Do not include explanations."
    ))
    
    messages = [system_msg]
    if chat_history:
        messages.extend(chat_history)
        
    messages.append(HumanMessage(content=f"Schema:\n{schema}\n\nQuestion: {question}\n\nSQL:"))
    
    for attempt in range(max_retries + 1):
        response = llm.invoke(messages)
        raw_sql = response.content
        cleaned_sql = clean_sql(raw_sql)
        
        messages.append(AIMessage(content=raw_sql))
        
        if not cleaned_sql:
            error_msg = "Could not extract SQL from your response. Please provide only the SQL."
            messages.append(HumanMessage(content=error_msg))
            continue
            
        df, err, t_ms = run_sql(conn, cleaned_sql)
        
        if err is None:
            # Success! Save to cache
            cache[q_key] = cleaned_sql
            save_cache(cache)
            return cleaned_sql, df, attempt, t_ms, None, False
        
        # Failed, self-heal
        if attempt < max_retries:
            error_prompt = f"Executing that SQL gave this error:\n{err}\nFix the query and return ONLY the corrected SQL."
            messages.append(HumanMessage(content=error_prompt))
            print(f"      [Retry {attempt+1}/{max_retries}] Fixing error: {err.splitlines()[-1][:60]}...")
        else:
            # Out of retries
            return cleaned_sql, None, attempt, t_ms, err, False

    return "", None, max_retries, 0.0, "max_retries_exceeded", False


def run_sql(conn, sql):
    """Run SQL on the DB. Returns (DataFrame, error_str, time_ms)."""
    start = time.perf_counter()
    
    # SECURITY GUARDRAIL: Block destructive queries
    upper_sql = sql.upper()
    dangerous_keywords = ["INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "TRUNCATE ", "REPLACE ", "CREATE "]
    if any(keyword in upper_sql for keyword in dangerous_keywords):
        t_ms = (time.perf_counter() - start) * 1000.0
        return None, "Security Error: Destructive SQL operations are strictly blocked. Only READ (SELECT) queries are permitted.", t_ms

    try:
        df = pd.read_sql_query(sql, conn)
        t_ms = (time.perf_counter() - start) * 1000.0
        return df, None, t_ms
    except Exception as e:
        t_ms = (time.perf_counter() - start) * 1000.0
        return None, str(e), t_ms


def analyze_query_performance(sql, schema, llm):
    """
    Acts as a Senior DBA to critique the generated SQL query.
    Returns a markdown string containing the optimization analysis.
    """
    sys_msg = SystemMessage(content=(
        "You are a Senior Database Administrator and Data Engineer. "
        "Analyze the provided SQL query against the schema for performance bottlenecks. "
        "Return a brief Markdown response with three sections: "
        "1. **Optimization Score**: Give a score out of 100. "
        "2. **Bottlenecks**: E.g. full table scans, missing JOIN optimizations, suboptimal aggregations. "
        "3. **Recommendations**: E.g. specific indexes to add, rewriting subqueries."
    ))
    messages = [
        sys_msg,
        HumanMessage(content=f"Schema:\n{schema}\n\nQuery:\n{sql}\n\nAnalysis:")
    ]
    response = llm.invoke(messages)
    return response.content


def gold_result_to_df(gold_result_json):
    """Rebuild the gold result DataFrame from the stored JSON."""
    obj = json.loads(gold_result_json)
    return pd.DataFrame(obj["rows"], columns=obj["columns"])


# ---------- the main flow ----------
def run_eval():
    schema = load_schema()
    golden = load_golden()
    conn = sqlite3.connect(DB_PATH)

    all_rows = []
    scoreboard = {}

    for name, slug in MODELS:
        print(f"\n{'='*60}\nMODEL: {name}  ({slug})\n{'='*60}")
        llm = make_llm(slug)          # 1. load the model
        correct = 0

        for _, g in golden.iterrows():
            qid = g["id"]
            question = g["question"]
            order_sensitive = str(g["order_sensitive"]).upper() == "TRUE"
            gold_df = gold_result_to_df(g["gold_result_json"])

            # 2 & 3. generate, execute and self-heal SQL
            try:
                gold_sql = g["gold_sql"]
                _, _, gold_time_ms = run_sql(conn, gold_sql)
                
                sql, gen_df, retries, gen_time_ms, gen_err = generate_and_heal_sql(question, schema, llm, conn)
            except Exception as e:
                print(f"  #{qid:2} [{g['difficulty']:6}] GEN-ERROR: {e}")
                all_rows.append(dict(model=name, id=qid, difficulty=g["difficulty"],
                                     correct=False, reason="gen_error", sql="",
                                     retries=0, gen_time_ms=0.0, gold_time_ms=0.0))
                continue

            # 4. evaluate
            if gen_df is None:
                verdict = {"correct": False, "reason": f"sql_error: {gen_err}"}
            else:
                verdict = evaluate_one(gold_df, gen_df, order_sensitive, gold_time_ms, gen_time_ms)
                
            if verdict["correct"]:
                correct += 1

            mark = "OK " if verdict["correct"] else "XX "
            print(f"  #{qid:2} [{g['difficulty']:6}] {mark} {verdict['reason']} (Retries: {retries})")
            all_rows.append(dict(model=name, id=qid, difficulty=g["difficulty"],
                                 correct=verdict["correct"], reason=verdict["reason"],
                                 sql=sql, retries=retries, 
                                 gen_time_ms=gen_time_ms, gold_time_ms=gold_time_ms))

        total = len(golden)
        scoreboard[name] = correct
        print(f"\n  SCORE: {correct}/{total} = {100*correct/total:.1f}%")

    conn.close()

    # 5. log final scores
    print(f"\n{'='*60}\nFINAL SCOREBOARD (execution accuracy)\n{'='*60}")
    total = len(golden)
    for name, _ in MODELS:
        c = scoreboard[name]
        print(f"  {name:18s} {c:2}/{total}  = {100*c/total:5.1f}%")

    pd.DataFrame(all_rows).to_csv(RESULTS_PATH, index=False)
    print(f"\nDetailed results saved -> {RESULTS_PATH}")


if __name__ == "__main__":
    if not API_KEY:
        print("Missing OPENROUTER_API_KEY - add it to your .env file")
    else:
        run_eval()