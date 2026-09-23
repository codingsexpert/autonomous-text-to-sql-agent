import streamlit as st
import sqlite3
import os
import plotly.express as px
from dotenv import load_dotenv

# Import LangChain message types for history
from langchain_core.messages import HumanMessage, AIMessage

# Import backend logic from our existing files
from main import make_llm, load_schema, generate_and_heal_sql, analyze_query_performance
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
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.session_state.lc_history = []
        st.rerun()
        
    st.markdown("---")
    st.markdown("**Powered by:**\n- LangChain\n- Groq\n- SQLite")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "lc_history" not in st.session_state:
    st.session_state.lc_history = []

# Display chat messages from history on app rerun
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            st.code(msg["sql"], language="sql")
        if "df" in msg and msg["df"] is not None:
            st.dataframe(msg["df"], use_container_width=True)
        if "fig" in msg and msg["fig"] is not None:
            st.plotly_chart(msg["fig"], use_container_width=True)
        if "insights" in msg and msg["insights"]:
            with st.expander("💡 Query Performance Insights"):
                st.markdown(msg["insights"])

# Main interface for chat input
if prompt := st.chat_input("Ask a question about IPL (2021-2024)..."):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Add user message to UI state
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("assistant"):
        with st.spinner("Agent is working (Generating SQL, running, and self-healing if needed)..."):
            # Initialize connections
            llm = make_llm(selected_slug)
            schema = load_schema()
            conn = sqlite3.connect("ipl_2021_2024.db")
            
            try:
                # Call our core agentic logic with chat_history
                sql, df, retries, exec_time, err = generate_and_heal_sql(
                    prompt, schema, llm, conn, chat_history=st.session_state.lc_history
                )
                
                if df is not None:
                    response_text = f"Data fetched successfully in {exec_time:.2f} ms with {retries} retries."
                    st.success(response_text)
                    st.code(sql, language="sql")
                    st.dataframe(df, use_container_width=True)
                    
                    fig = None
                    # Auto-Charts Logic
                    import pandas as pd
                    
                    if len(df) > 0 and len(df.columns) >= 2:
                        # SQLite COUNT(*) often returns as object/string. We must coerce to numeric where possible.
                        for col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='ignore')
                            
                        numerics = df.select_dtypes(include=['number']).columns.tolist()
                        categoricals = df.select_dtypes(exclude=['number']).columns.tolist()
                        
                        if len(numerics) > 0 and len(categoricals) > 0:
                            x_col = categoricals[0]
                            y_col = numerics[0]
                            
                            # Sort the dataframe for better visualization
                            chart_df = df.sort_values(by=y_col, ascending=False).head(20)
                            
                            # Choose chart type dynamically
                            if chart_df[x_col].nunique() <= 7:
                                # Donut chart for few categories
                                fig = px.pie(chart_df, names=x_col, values=y_col, hole=0.4,
                                             title=f"<b>{y_col.title()} by {x_col.title()}</b>",
                                             color_discrete_sequence=px.colors.qualitative.Pastel)
                                fig.update_traces(textposition='inside', textinfo='percent+label')
                            else:
                                # Beautiful Bar chart for many categories
                                fig = px.bar(chart_df, x=x_col, y=y_col, 
                                             title=f"<b>Top {len(chart_df)} {x_col.title()} by {y_col.title()}</b>",
                                             color=y_col, color_continuous_scale="Viridis")
                                
                            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", 
                                              margin=dict(t=50, l=20, r=20, b=20))
                            st.plotly_chart(fig, use_container_width=True)
                            
                        elif len(numerics) >= 2:
                            x_col = numerics[0]
                            y_col = numerics[1]
                            fig = px.area(df, x=x_col, y=y_col, title=f"<b>{y_col.title()} vs {x_col.title()}</b>",
                                          color_discrete_sequence=["#00b4d8"])
                            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", 
                                              margin=dict(t=50, l=20, r=20, b=20))
                            st.plotly_chart(fig, use_container_width=True)
                            
                    # --- QUERY PERFORMANCE OPTIMIZER ---
                    with st.spinner("Analyzing query performance..."):
                        insights = analyze_query_performance(sql, schema, llm)
                        
                    with st.expander("💡 Query Performance Insights"):
                        st.markdown(insights)

                    # Save assistant response to UI state
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "sql": sql,
                        "df": df,
                        "fig": fig,
                        "insights": insights
                    })

                    
                    # Save context to LangChain history
                    st.session_state.lc_history.append(HumanMessage(content=prompt))
                    st.session_state.lc_history.append(AIMessage(content=sql))
                    
                else:
                    error_text = f"Failed to generate valid SQL within the retry limit.\nError: {err}"
                    st.error(error_text)
                    st.code(sql, language="sql")
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_text,
                        "sql": sql
                    })
            
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
            finally:
                conn.close()
