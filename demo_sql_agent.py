import sqlite3
import re
from dotenv import load_dotenv
from groq import Groq
from engine import StateGraph, END
from checkpoint import MemoryCheckpointer

load_dotenv()
groq_client = Groq(timeout=20.0)
MODEL_NAME = "openai/gpt-oss-20b"


def extract_sql_query(raw_text: str) -> str:
    """Extracts raw SQL from markdown blocks if present."""
    match = re.search(r"```(?:sql)?\s*(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
    clean = match.group(1).strip() if match else raw_text.strip()
    return clean.replace(";", "")  # standardize without trailing semicolons


# =====================================================================
# NODE 1: SQL GENERATOR
# =====================================================================
def sql_generator_node(state: dict) -> dict:
    """LLM Persona: Generates a SQL query. If state contains a previous error,
    it reads the error message and attempts to self-correct."""
    system_prompt = (
        "You are an expert SQLite developer.\n"
        "Generate a single valid SQLite query to answer the user's question.\n"
        "Return ONLY the SQL query inside ```sql ... ``` fences. No commentary."
    )

    error_context = ""
    if state.get("error"):
        error_context = (
            f"\nPREVIOUS ATTEMPT FAILED WITH ERROR:\n{state['error']}\n"
            f"PREVIOUS FAILING QUERY:\n{state.get('sql_query')}\n"
            "Fix the query to eliminate this SQLite error."
        )

    user_prompt = (
        f"TABLE SCHEMA:\n{state['schema']}\n"
        f"QUESTION: {state['question']}"
        f"{error_context}"
    )
    response = groq_client.chat.completions.create(
    model=MODEL_NAME,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
         
    ],
    temperature=0.0, 
    )
    raw_sql = response.choices[0].message.content or ""
    clean_sql = extract_sql_query(raw_sql)

    return{
        "sql_query": clean_sql,
         "attempts": state["attempts"] + 1
         }

# =====================================================================
# NODE 2: SQL EXECUTOR
# =====================================================================
def sql_executor_node(state: dict) -> dict:
    """Executes state['sql_query'] against company.db in SQLite."""

    conn = sqlite3.connect("company.db")
    cursor = conn.cursor()

    if not state["sql_query"].strip().upper().startswith("SELECT"):
        return {"result": None, "error": "SecurityPolicyError: Only SELECT queries are permitted."}

    try:
        cursor.execute(state["sql_query"])
        rows = cursor.fetchall()

        return {"result": rows, "error": None}

    except sqlite3.Error as e:
        return {"result": None, "error": str(e)}

    finally:
        conn.close()


# =====================================================================
# CONDITIONAL EDGE: ROUTER
# =====================================================================
def should_continue_router(state: dict) -> str:
    """Decides whether to retry generator_node or terminate at END."""

    if state["error"] is None:
        return END
    if state["attempts"] >= 3:
        return END
    
    return "sql_generator"

# =====================================================================
# WORKFLOW GRAPH BUILDER
# =====================================================================
def build_sql_agent() -> StateGraph:
    """Constructs and returns the compiled nano-graph SQL agent."""
    cp = MemoryCheckpointer()
    graph = StateGraph(checkpointer=cp)

    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.set_entry_point("sql_generator")
    graph.add_edge("sql_generator", "sql_executor")
    graph.add_conditional_edge("sql_executor", should_continue_router)
    return graph
 
if __name__ == "__main__":
    SCHEMA = "CREATE TABLE employees (id INTEGER, name TEXT, department TEXT, salary REAL);"
    
    agent = build_sql_agent()

    initial_input = {
        "question": "Which employees work in Engineering and make more than 80,000 dollars?",
        "schema": SCHEMA,
        "attempts": 0,
        "error": None,
        "result": None,
        "sql_query": ""
    }

    print("\n🚀 [nano-graph] Running Text-to-SQL Self-Correcting Agent...")
    final_output = agent.invoke(initial_input, thread_id="query_run_1")

    print("\n================ FINAL STATE ================")
    print(f"Generated SQL: {final_output.get('sql_query')}")
    print(f"Query Result:  {final_output.get('result')}")
    print(f"Total Cycles:  {final_output.get('attempts')}")
    print(f"Graph Trace:   {' -> '.join(final_output.get('_trace', []))}")