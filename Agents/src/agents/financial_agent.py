import os
import json
import pandas as pd
from pathlib import Path
from langchain.schema import HumanMessage
from ..utils.llm_wrapper import llm
from ..utils.file_utils import load_json_file
from ..utils.summarizer import summarize_result
from ..computations.financial_data_generator import run_financial_computation


DATA_PATH = Path(os.getenv("DATA_PATH", "output"))
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

_dataframes_cache = {}


FINANCIAL_SCHEMAS = {
    "overdue_payments.json": {
        "company_id": "int",
        "company_name": "str",
        "contact_person": "str",
        "contact_email": "str",
        "payment_id": "int",
        "invoice_month": "str (YYYY-MM)",
        "amount_due": "float",
        "due_date": "str (YYYY-MM-DD)",
        "days_overdue": "int",
        "status": "str (Only companies with 'Overdue' is present)"
    },
    "delayed_payments.json": {
        "company_id": "int",
        "company_name": "str",
        "contact_person": "str",
        "contact_email": "str",
        "payment_id": "int",
        "invoice_month": "str (YYYY-MM)",
        "amount_due": "float",
        "due_date": "str (YYYY-MM-DD)",
        "payment_date": "str (YYYY-MM-DD)",
        "days_delayed": "int",
        "status": "str (Only companies with status 'Paid' but paid after due date)",
        "delay_penalty_applied": "float (penalty amount calculated based on delay)"
    },
    "price_revisions.json": {
        "company_id": "int",
        "company_name": "str",
        "contact_person": "str",
        "contact_email": "str",
        "endpoints_scale": "int",
        "happiness_score": "float",
        "tickets_raised": "int",
        "contract_length_years": "int",
        "avg_payment_delay_days": "float",
        "current_monthly_cost": "float",
        "revision_factor": "float",
        "revision_percentage": "str (for example - '18.05%')", 
        "revised_monthly_cost": "float",
        "annual_cost_change": "float",
        "factor_breakdown": {
            "base_inflation": "float",
            "ticket_volume_impact": "float",
            "endpoint_scale_impact": "float",
            "payment_delay_penalty": "float",
            "happiness_adjustment": "float",
            "contract_length_discount": "float"
        }
    },
    "upcoming_due_dates.json": {
        "company_id": "int",
        "company_name": "str",
        "contact_person": "str",
        "contact_email": "str",
        "payment_id": "int",
        "invoice_month": "str (YYYY-MM)",
        "amount_due": "float",
        "due_date": "str (YYYY-MM-DD)",
        "days_until_due": "int",
        "status": "str (Only companies with status 'Pending' is present)"
    }
}


def load_all_dataframes():
    """
    Loads all financial datasets into pandas dataframes and caches them
    """
    global _dataframes_cache
    
    if _dataframes_cache:
        return _dataframes_cache
    
    run_financial_computation()
    
    dataframes = {}
    
    for name in FINANCIAL_SCHEMAS.keys():
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
    
    prompt = f"""You are a pandas expert analyzing MSP financial data. Generate Python code to answer the user's query.

AVAILABLE DATAFRAMES:
{json.dumps(df_info, indent=2, default=str)}

SCHEMA REFERENCE:
{json.dumps(FINANCIAL_SCHEMAS, indent=2)}

DATASET DESCRIPTIONS:
- overdue_payments: Companies with status "Overdue" (haven't paid yet, past due date)
- delayed_payments: Companies with status "Paid" but paid after due date
- upcoming_due_dates: Companies with status "Pending" (not yet due or due soon)
- price_revisions: Revised pricing for customers with activity breakdown

IMPORTANT NOTES:
1. Dataframes available as: overdue_payments, delayed_payments, price_revisions, upcoming_due_dates
2. The 'factor_breakdown' column in price_revisions contains nested dictionaries
3. ALL utilities are available: pd, json, numpy as np

WORKING WITH NESTED DICTIONARIES (factor_breakdown):
- To extract specific fields from nested dicts:
  
  # Extract single field from nested dict:
  result = price_revisions.copy()
  result['base_inflation'] = result['factor_breakdown'].apply(lambda x: x.get('base_inflation', 0))
  
  # Flatten entire nested dict into separate columns:
  breakdown_df = pd.json_normalize(price_revisions['factor_breakdown'].tolist())
  result = pd.concat([price_revisions.drop('factor_breakdown', axis=1), breakdown_df], axis=1)
  
  # Filter based on nested dict values:
  result = price_revisions[
      price_revisions['factor_breakdown'].apply(lambda x: x.get('ticket_volume_impact', 0) > 0.05)
  ]
  
  # Merge with breakdown expanded:
  breakdown_df = pd.json_normalize(price_revisions['factor_breakdown'].tolist())
  breakdown_df.columns = ['breakdown_' + col for col in breakdown_df.columns]
  result = pd.concat([price_revisions, breakdown_df], axis=1)

USER QUERY:
"{user_query}"

REQUIREMENTS:
- Return ONLY executable Python code (no markdown, no explanations, no comments)
- MUST assign final result to variable named 'result'
- Result MUST be a single DataFrame (never a list of DataFrames)
- Use clear, descriptive operations
- Handle missing values gracefully
- The code will be executed with pd, json, and np already imported

EXAMPLES:
result = overdue_payments[overdue_payments['days_overdue'] > 10]
result = delayed_payments.sort_values('days_delayed', ascending=False).head(10)
result = price_revisions[['company_name', 'revision_percentage', 'annual_cost_change']]
result = overdue_payments.merge(price_revisions, on='company_id', how='inner')
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
        
        if all(isinstance(item, pd.DataFrame) for item in result):
            return pd.concat(result, ignore_index=True)
        
        if isinstance(result[0], dict):
            return pd.DataFrame(result)
        
        return pd.DataFrame({'value': result})
    
    return pd.DataFrame({'result': [result]})


def handle_financial_query(user_query: str):
    """
    Handles financial queries end-to-end:
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
