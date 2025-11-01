import os
import json
import sqlite3
import pandas as pd
from pathlib import Path
from langchain.schema import HumanMessage
from ..utils.llm_wrapper import llm
from ..utils.summarizer import summarize_result


DB_PATH = Path("databases/msp_data.db")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")


_dataframes_cache = {}


MSP_INSIGHTS_SCHEMAS = {
    "company_contract": {
        "company_id": "int (PRIMARY KEY)",
        "company_name": "str",
        "contract_status": "str (Active/Expired)",
        "total_tickets": "int",
        "annual_revenue": "float"
    },
    "companies": {
        "company_id": "int (PRIMARY KEY)",
        "company_name": "str",
        "contact_person": "str",
        "contact_email": "str",
        "contract_start_date": "str (YYYY-MM-DD)",
        "contract_end_date": "str (YYYY-MM-DD)",
        "contract_length_years": "int",
        "endpoints_scale": "int",
        "happiness_score": "float",
        "tickets_raised": "int",
        "sla_agreement_ticket_categories": "str (JSON array of category names)"
    },
    "payments": {
        "payment_id": "int (PRIMARY KEY)",
        "company_id": "int",
        "invoice_month": "str (YYYY-MM)",
        "amount_due": "float",
        "amount_paid": "float",
        "due_date": "str (YYYY-MM-DD)",
        "payment_date": "str (YYYY-MM-DD)",
        "status": "str (Paid/Pending/Overdue)"
    },
    "technicians": {
        "technician_id": "int (PRIMARY KEY)",
        "name": "str",
        "email": "str",
        "specialization": "str",
        "tickets_assigned": "int",
        "active_status": "int (0=inactive, 1=active)",
        "created_at": "str (ISO datetime)",
        "pending_ticket_count": "int (default 0)"
    },
    "customer_company_employees": {
        "employee_id": "int (PRIMARY KEY)",
        "company_id": "int",
        "name": "str",
        "email": "str",
        "department": "str",
        "role": "str",
        "location": "str",
        "date_joined": "str",
        "assigned_software": "str (JSON array)"
    },
    "software_inventory": {
        "software_id": "str (PRIMARY KEY)",
        "name": "str",
        "category": "str",
        "license_cost_usd": "float",
        "license_type": "str",
        "license_expiry": "str (YYYY-MM-DD)",
        "vendor": "str"
    },
    "ticket_categories": {
        "category_id": "int (PRIMARY KEY)",
        "category_name": "str",
        "description": "str"
    },
    "ticket_category_count": {
        "count_id": "int (PRIMARY KEY)",
        "company_id": "int",
        "category_id": "int",
        "total_tickets": "int",
        "last_updated": "str (YYYY-MM-DD HH:MM:SS)"
    }
}

def load_all_dataframes():
    """
    Loads only the predefined schema tables into pandas dataframes and caches them
    """
    global _dataframes_cache
    
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    
    if _dataframes_cache:
        return _dataframes_cache
    
    conn = sqlite3.connect(DB_PATH)
    try:
        for table_name in MSP_INSIGHTS_SCHEMAS.keys():
            try:
                df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
                _dataframes_cache[table_name] = df
                print(f"Loaded table '{table_name}' with shape {df.shape}")
            except Exception as e:
                print(f"Warning: Error loading table '{table_name}': {e}")
        
        return _dataframes_cache
    finally:
        conn.close()



def convert_to_pandas_query(user_query: str, dataframes: dict):
    """
    Uses LLM to convert natural language query into pandas operations
    """
    df_info = {}
    for table_name, df in dataframes.items():
        df_info[table_name] = {
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "sample_data": df.head(2).to_dict('records') if not df.empty else []
        }
    
    prompt = f"""You are a pandas expert analyzing MSP business data. Generate Python code to answer the user's query.

AVAILABLE DATAFRAMES:
{json.dumps(df_info, indent=2, default=str)}

SCHEMA REFERENCE:
{json.dumps(MSP_INSIGHTS_SCHEMAS, indent=2)}

IMPORTANT DATA NOTES:
1. JSON Fields:
   - customer_company_employees.assigned_software: JSON array of objects
     Example: [{{"name": "Microsoft Excel", "license_type": "Office365"}}]
   - companies.sla_agreement_ticket_categories: String representation of list
     Example: ["Network & Connectivity Support", "Hardware Maintenance & Repair"]

2. Ticket Data:
   - ticket_category_count: Aggregated counts per company per category
   - ticket_categories: Category definitions (join on category_id)
   - companies.tickets_raised: Total tickets raised by company

3. Business Logic:
   - Profitability = annual_revenue - (tickets × $25) - (employee software costs)
   - Upselling opportunities: Compare sla_agreement_ticket_categories vs ticket_category_count
   - active_status in technicians: 0=inactive, 1=active

4. ALL utilities available: pd, json, numpy as np

HANDLING OVERLAPPING COLUMNS (CRITICAL):
Multiple dataframes share these columns:
- company_id: company_contract, companies, payments, customer_company_employees, ticket_category_count
- company_name: company_contract, companies
- name: technicians, customer_company_employees, software_inventory
- email: technicians, customer_company_employees

MERGE STRATEGIES - Choose the best approach:

A) Use suffixes (recommended for most cases):
   companies.merge(payments, on='company_id', suffixes=('_co', '_pay'))
   technicians.rename(columns={{'name': 'tech_name'}}).merge(
       customer_company_employees.rename(columns={{'name': 'emp_name'}}),
       left_on='tech_email', right_on='emp_email'
   )

B) Select specific columns before merge:
   companies[['company_id', 'company_name', 'happiness_score']].merge(
       payments[['company_id', 'amount_paid', 'status']], 
       on='company_id'
   )

C) Rename before merge:
   co = companies.rename(columns={{'company_name': 'co_name'}})
   result = co.merge(company_contract.rename(columns={{'company_name': 'contract_name'}}), on='company_id')

WORKING WITH JSON FIELDS:

# Parse assigned_software JSON:
import json
emp_df = customer_company_employees.copy()
emp_df['software_list'] = emp_df['assigned_software'].apply(
    lambda x: json.loads(x) if isinstance(x, str) else []
)
emp_df['software_names'] = emp_df['software_list'].apply(
    lambda x: [s.get('name', '') for s in x] if isinstance(x, list) else []
)

# Parse sla_agreement_ticket_categories:
import json
companies_df = companies.copy()
companies_df['sla_categories'] = companies_df['sla_agreement_ticket_categories'].apply(
    lambda x: json.loads(x) if isinstance(x, str) else []
)

USER QUERY:
"{user_query}"

REQUIREMENTS:
- Return ONLY executable Python code (no markdown, no explanations, no comments)
- MUST assign final result to variable named 'result'
- Always handle overlapping columns when using merge()
- Use descriptive column names in output
- Handle JSON fields appropriately if needed
- The code will be executed with pd, json, and np already imported

EXAMPLES:
result = companies[companies['happiness_score'] > 8.0]
result = companies.merge(payments, on='company_id', suffixes=('_co', '_pay'))
result = technicians[technicians['active_status'] == 1][['name', 'specialization']]
result = payments.groupby('company_id')['amount_paid'].sum().reset_index()
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
        
        namespace.update(dataframes)
        
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
        
        if "columns overlap" in str(e).lower():
            error_msg += "\n\nTIP: This error occurs when merging DataFrames with overlapping column names."
            error_msg += "\nThe LLM should add suffixes parameter to merge operations."
        elif "key error" in str(e).lower():
            error_msg += "\n\nTIP: A column name may be incorrect or doesn't exist in the DataFrame."
        
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
        has_complex = any(isinstance(v, (pd.DataFrame, pd.Series)) for v in result.values())
        
        if has_complex:
            converted = {}
            for key, value in result.items():
                if isinstance(value, pd.DataFrame):
                    converted[key] = value.to_dict('records')
                elif isinstance(value, pd.Series):
                    converted[key] = value.to_dict()
                else:
                    converted[key] = value
            return pd.DataFrame([converted])
        else:
            if any(isinstance(v, (list, tuple)) for v in result.values()):
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



def handle_msp_insights_query(user_query: str):
    """
    Handles MSP insights queries end-to-end:
    Load data → Generate code → Execute → Summarize
    """
    
    if not DB_PATH.exists():
        return f"Error: Database not found at {DB_PATH}"
    
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
