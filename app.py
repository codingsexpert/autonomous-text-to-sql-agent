import streamlit as st
import sqlite3
import os
import plotly.express as px
from dotenv import load_dotenv

# Import backend logic from our existing files
from main import make_llm, load_schema, generate_and_heal_sql
from models import MODELS

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(page_title="Text-to-SQL Agent", layout="wide")

st.title("Autonomous Text-to-SQL Agent")
st.markdown("Ask a question in plain English, and the AI will write the SQL, heal any errors, and fetch the data from the IPL Database.")

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    
    # Check API Key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("Missing GROQ_API_KEY. Please add it to your .env file in this directory.")
        st.stop()
        
    model_options = {name: slug for name, slug in MODELS}
    selected_model_name = st.selectbox("Select AI Model", options=list(model_options.keys()))
    selected_slug = model_options[selected_model_name]
    
    st.info(f"Currently using: `{selected_slug}`")
    st.markdown("---")
    st.markdown("**Powered by:**\n- LangChain\n- Groq\n- SQLite")

# Main interface
question = st.text_input("Ask a question about IPL (2021-2024):", placeholder="e.g., Which player scored the most runs overall?")

if st.button("Generate SQL & Run", type="primary"):
    if not question.strip():
        st.warning("Please enter a question first.")
    else:
        with st.spinner("Agent is working (Generating SQL, running, and self-healing if needed)..."):
            # Initialize connections
            llm = make_llm(selected_slug)
            schema = load_schema()
            conn = sqlite3.connect("ipl_2021_2024.db")
            
            try:
                # Call our core agentic logic
                sql, df, retries, exec_time, err = generate_and_heal_sql(question, schema, llm, conn)
                
                if df is not None:
                    st.success("Data fetched successfully!")
                    
                    # Display metrics in columns
                    col1, col2 = st.columns(2)
                    col1.metric("Execution Time (ms)", f"{exec_time:.2f}")
                    col2.metric("Self-Healing Retries", retries)
                    
                    # Display SQL and Data
                    st.subheader("Generated SQL:")
                    st.code(sql, language="sql")
                    
                    st.subheader("Result Data:")
                    st.dataframe(df, use_container_width=True)
                    
                    # Auto-Charts Logic
                    if len(df) > 0 and len(df.columns) >= 2:
                        numerics = df.select_dtypes(include=['number']).columns.tolist()
                        categoricals = df.select_dtypes(exclude=['number']).columns.tolist()
                        
                        if len(numerics) > 0 and len(categoricals) > 0:
                            x_col = categoricals[0]
                            y_col = numerics[0]
                            
                            st.subheader("Visualization:")
                            # If many rows, maybe limit or just plot
                            if len(df) > 50:
                                st.info("Showing top 50 rows in chart for better readability.")
                                chart_df = df.head(50)
                            else:
                                chart_df = df
                                
                            fig = px.bar(chart_df, x=x_col, y=y_col, title=f"{y_col.title()} by {x_col.title()}",
                                         template="plotly_white", color=x_col)
                            st.plotly_chart(fig, use_container_width=True)
                        elif len(numerics) >= 2:
                            x_col = numerics[0]
                            y_col = numerics[1]
                            st.subheader("Visualization:")
                            fig = px.line(df, x=x_col, y=y_col, title=f"{y_col.title()} vs {x_col.title()}",
                                          template="plotly_white")
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("Failed to generate valid SQL within the retry limit.")
                    st.subheader("Last Generated SQL:")
                    st.code(sql, language="sql")
                    st.subheader("Error Message from Database:")
                    st.error(err)
                    st.metric("Retries Exhausted", retries)
            
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
            finally:
                conn.close()
