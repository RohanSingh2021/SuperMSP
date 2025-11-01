import os
import json
import pandas as pd
from pathlib import Path
from langchain.schema import HumanMessage
from ..utils.llm_wrapper import llm
from ..utils.file_utils import load_json_file
from ..utils.summarizer import summarize_result
from ..computations.company_ticket_data_generator import run_company_ticket_computation


DATA_PATH = Path(os.getenv("DATA_PATH", "output"))
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

_dataframes_cache = {}


COMPANY_TICKET_SCHEMAS = {
    "company_analysis.json": {
        "company_id": "int",
        "company_name": "str",
        "resolved_tickets": "int",
        "average_resolution_time_hours": "float",
        "employee_satisfaction": "float",
        "tickets_by_category": "dict (category_name(str): ticket_count(int))"
    }
}

ALLOWED_CATEGORIES = [
    "Network Connectivity Issue",
    "Hardware Failure",
    "Software Application Error",
    "Password Reset",
    "VPN Access Problem",
    "Printer Issue",
    "Email & Collaboration Tool Issue",
    "Permission & Access Request",
    "New User Setup",
    "Virus or Malware Concern",
    "Software Installation Request",
    "General Inquiry"
]


def load_all_dataframes():
    """
    Loads all company ticket datasets into pandas dataframes and caches them
    """
    global _dataframes_cache
    
    if _dataframes_cache:
        return _dataframes_cache
    
    run_company_ticket_computation(DATA_PATH)
    
    dataframes = {}
    
    for name in COMPANY_TICKET_SCHEMAS.keys():
        file_path = DATA_PATH / name
        if file_path.exists():
            try:
                data = load_json_file(file_path)
                df = pd.DataFrame(data if isinstance(data, list) else [data])
                dataframes[name] = df
                print(f"Loaded dataset '{name}' with shape {df.shape}")
            except Exception as e:
                print(f"Warning: Could not load {name}: {e}")
        else:
            print(f"Warning: Dataset '{name}' not found in {DATA_PATH}")
    
    if not dataframes:
        raise Exception("No datasets could be loaded.")
    
    _dataframes_cache = dataframes
    return _dataframes_cache



def convert_to_pandas_query(user_query: str, dataframes: dict):
    """
    Uses LLM to convert natural language query into pandas operations
    """
    df_info = {}
    for dataset_name, df in dataframes.items():
        df_info[dataset_name] = {
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "sample_data": df.head(2).to_dict('records') if not df.empty else []
        }
    
    prompt = f"""You are a pandas expert. Generate Python code to answer the user's query.

AVAILABLE DATAFRAMES:
{json.dumps(df_info, indent=2, default=str)}

SCHEMA REFERENCE:
{json.dumps(COMPANY_TICKET_SCHEMAS, indent=2)}

ALLOWED TICKET CATEGORIES:
{json.dumps(ALLOWED_CATEGORIES, indent=2)}

IMPORTANT NOTES:
1. The dataframe is available as: company_analysis
2. The 'tickets_by_category' field is a dictionary where keys are category names and values are counts
3. ALL utilities are available: pd, json, numpy as np

WORKING WITH DICTIONARIES:
- To extract values from dict columns, use these patterns:
  
  # Get sum of specific category across all rows:
  result = sum(row.get('Category Name', 0) for row in company_analysis['tickets_by_category'])
  
  # Flatten dictionary column into separate columns:
  tickets_df = pd.json_normalize(company_analysis['tickets_by_category'].tolist())
  result = pd.concat([company_analysis, tickets_df], axis=1)
  
  # Create new column from dict value:
  result = company_analysis.copy()
  result['specific_category'] = result['tickets_by_category'].apply(lambda x: x.get('Category Name', 0))
  
  # Sum all values in each dictionary:
  result = company_analysis.copy()
  result['total_tickets'] = result['tickets_by_category'].apply(lambda x: sum(x.values()))

USER QUERY:
"{user_query}"

REQUIREMENTS:
- Return ONLY executable Python code (no markdown, no explanations, no comments)
- MUST assign final result to variable named 'result'
- Use clear, descriptive operations
- Handle missing values gracefully
- The code will be executed with pd, json, and np already imported

EXAMPLES:
result = company_analysis.sort_values('employee_satisfaction', ascending=False).head(10)
result = company_analysis[company_analysis['resolved_tickets'] > 100]
result = sum(row.get('Network Connectivity Issue', 0) for row in company_analysis['tickets_by_category'])
"""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    pandas_code = response.content.strip()
    
    pandas_code = pandas_code.replace("```python", "").replace("```", "").strip()
    
    return pandas_code



def execute_pandas_query(pandas_code: str, dataframes: dict):
    """
    Executes the pandas code with full access to necessary libraries and utilities
    """
    try:
        namespace = {
            'pd': pd,
            'json': json,
            'ALLOWED_CATEGORIES': ALLOWED_CATEGORIES,
        }
        
        try:
            import numpy as np
            namespace['np'] = np
        except ImportError:
            pass
        
        for dataset_name, df in dataframes.items():
            var_name = dataset_name.split('.')[0]  
            namespace[var_name] = df
        
        exec(pandas_code, namespace)
        
        if 'result' not in namespace:
            raise Exception(
                "Generated code must assign output to variable named 'result'. "
                f"Generated code:\n{pandas_code}"
            )
        
        result = namespace['result']
        
        result_df = _normalize_to_dataframe(result)
        
        return result_df
        
    except Exception as e:
        error_msg = f"Error executing pandas query: {str(e)}\n\nGenerated code:\n{pandas_code}"
        raise Exception(error_msg)


def _normalize_to_dataframe(result):
    """
    Converts various result types to a pandas DataFrame
    """
    if isinstance(result, pd.DataFrame):
        return result
    
    if isinstance(result, pd.Series):
        return result.to_frame()
    
    if isinstance(result, dict):
        if any(isinstance(v, (list, tuple, pd.Series)) for v in result.values()):
            return pd.DataFrame(result)
        else:
            return pd.DataFrame([result])
    
    if isinstance(result, (list, tuple)):
        if len(result) == 0:
            return pd.DataFrame()
        if isinstance(result[0], dict):
            return pd.DataFrame(result)
        return pd.DataFrame({'value': result})
    
    return pd.DataFrame({'result': [result]})


def handle_company_ticket_query(user_query: str):
    """
    Handles company ticket queries end-to-end:
    Load data → Generate code → Execute → Summarize
    """
    
    try:
        dataframes = load_all_dataframes()
        print(f"\nLoaded {len(dataframes)} dataframes")
    except Exception as e:
        return f"Warning: Error loading dataframes: {e}"
    
    try:
        pandas_code = convert_to_pandas_query(user_query, dataframes)
        print(f"\nGenerated pandas code:\n{pandas_code}\n")
    except Exception as e:
        return f"Warning: Error generating pandas query: {e}"
    
    try:
        df_result = execute_pandas_query(pandas_code, dataframes)
        print(f"Query executed successfully. Result shape: {df_result.shape}")
    except Exception as e:
        return f"Warning: {str(e)}"
    
    if df_result.empty:
        return f"ℹ️ No results found for your query: '{user_query}'"
    
    try:
        summary = summarize_result(user_query, df_result)
        return summary
    except Exception as e:
        return f"Warning: Error summarizing results: {e}\n\nRaw results:\n{df_result.to_string()}"



def execute_direct_pandas_query(pandas_code: str):
    """
    Execute pandas queries directly without LLM (for testing/debugging)
    """
    try:
        dataframes = load_all_dataframes()
        df_result = execute_pandas_query(pandas_code, dataframes)
        print(f"\nQuery Results ({df_result.shape[0]} rows, {df_result.shape[1]} columns):")
        print(df_result.to_string())
        return df_result
    except Exception as e:
        print(f"Error: {e}")
        return None


def clear_dataframes_cache():
    """
    Clears the dataframes cache to force reload from database
    """
    global _dataframes_cache
    _dataframes_cache = {}
    print("Dataframes cache cleared")
