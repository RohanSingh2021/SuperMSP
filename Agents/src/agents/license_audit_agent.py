import os
import json
import pandas as pd
from pathlib import Path
from langchain.schema import HumanMessage
from ..utils.llm_wrapper import llm
from ..utils.file_utils import load_json_file
from ..utils.summarizer import summarize_result
from ..computations.license_audit_data_generator import run_license_audit_computation


DATA_PATH = Path(os.getenv("DATA_PATH", "output"))
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

_dataframes_cache = {}

LICENSE_SCHEMAS = {
    "flagged_anomalous_access.json": {
        "employee_id": "int",
        "employee_name": "str",
        "role": "str",
        "software_name": "str",
        "software_key": "str",
        "license_type": "str",
        "license_cost_usd": "float",
        "reason": "str (e.g., 'Role not typically allowed to use this software')"
    },
    "flagged_unused_software.json": {
        "employee_id": "int",
        "employee_name": "str",
        "software_name": "str",
        "software_key": "str",
        "last_used_iso": "str (ISO 8601 datetime format)",
        "days_since_last_use": "int value or 'NEVER_USED'",
        "license_cost_usd": "float",
        "reason": "str (e.g., 'No usage in 60 days')"
    }
}

ALLOWED_ROLES = [
    "UI/UX Designer", "Sales Manager", "Sales Executive", "QA Engineer",
    "Associate Product Manager", "Product Manager", "Operations Manager",
    "IT Support Engineer", "Recruiter", "HR Manager", "Graphic Designer",
    "Frontend Developer", "Financial Analyst", "Digital Marketing Specialist",
    "DevOps Engineer", "Data Scientist", "Data Analyst", "Content Writer",
    "Backend Developer", "Accounts Executive"
]


def load_all_dataframes():
    """
    Loads all license audit datasets into pandas dataframes and caches them
    """
    global _dataframes_cache
    
    if _dataframes_cache:
        return _dataframes_cache
    
    run_license_audit_computation(DATA_PATH)
    
    dataframes = {}
    
    for name in LICENSE_SCHEMAS.keys():
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
    
    prompt = f"""You are a pandas expert analyzing license audit data. Generate Python code to answer the user's query.

AVAILABLE DATAFRAMES:
{json.dumps(df_info, indent=2, default=str)}

SCHEMA REFERENCE:
{json.dumps(LICENSE_SCHEMAS, indent=2)}

ALLOWED ROLES:
{json.dumps(ALLOWED_ROLES, indent=2)}

IMPORTANT NOTES:
1. Dataframes available as: flagged_anomalous_access, flagged_unused_software
2. The 'days_since_last_use' field can contain:
   - Integer values (e.g., 30, 45, 90)
   - String value "NEVER_USED"
3. ALL utilities are available: pd, json, numpy as np, ALLOWED_ROLES list

WORKING WITH MIXED TYPE COLUMNS (days_since_last_use):
- This column contains both integers and the string "NEVER_USED"
- To filter for never used software:
  result = flagged_unused_software[flagged_unused_software['days_since_last_use'] == 'NEVER_USED']
  
- To filter for numeric values (used but inactive):
  result = flagged_unused_software[flagged_unused_software['days_since_last_use'] != 'NEVER_USED']
  result = result[result['days_since_last_use'] > 60]
  
- To include both never used AND long inactive:
  result = flagged_unused_software[
      (flagged_unused_software['days_since_last_use'] == 'NEVER_USED') |
      (flagged_unused_software['days_since_last_use'] > 90)
  ]
  
- To convert for calculations (handle NEVER_USED as high number):
  df_copy = flagged_unused_software.copy()
  df_copy['days_numeric'] = df_copy['days_since_last_use'].apply(
      lambda x: 999999 if x == 'NEVER_USED' else int(x)
  )
  result = df_copy.sort_values('days_numeric', ascending=False)

USER QUERY:
"{user_query}"

REQUIREMENTS:
- Return ONLY executable Python code (no markdown, no explanations, no comments)
- MUST assign final result to variable named 'result'
- Use clear, descriptive operations
- Handle mixed data types in days_since_last_use column
- The code will be executed with pd, json, np, and ALLOWED_ROLES already available

EXAMPLES:
result = flagged_anomalous_access[flagged_anomalous_access['role'] == 'Sales Manager']
result = flagged_unused_software[flagged_unused_software['days_since_last_use'] == 'NEVER_USED']
result = flagged_anomalous_access.groupby('role')['license_cost_usd'].sum().reset_index()
result = flagged_unused_software.sort_values('license_cost_usd', ascending=False).head(10)
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
            'ALLOWED_ROLES': ALLOWED_ROLES,
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



def handle_license_audit_query(user_query: str):
    """
    Handles license audit queries end-to-end:
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
