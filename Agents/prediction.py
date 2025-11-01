import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from datetime import datetime
import json
import os
import pickle
import hashlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "data", "revenue_data.json")
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")

def get_data_hash(data):
    """
    Generate a hash of the data to check if it has changed.
    """
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.md5(data_str.encode()).hexdigest()

def load_cached_models(data_hash):
    """
    Load cached models if they exist and match the data hash.
    Returns (revenue_model, tickets_model, processed_data) or (None, None, None) if not found.
    """
    try:
        revenue_model_path = os.path.join(MODELS_DIR, f"revenue_model_{data_hash}.pkl")
        tickets_model_path = os.path.join(MODELS_DIR, f"tickets_model_{data_hash}.pkl")
        data_path = os.path.join(MODELS_DIR, f"processed_data_{data_hash}.pkl")
        
        if all(os.path.exists(path) for path in [revenue_model_path, tickets_model_path, data_path]):
            with open(revenue_model_path, 'rb') as f:
                revenue_model = pickle.load(f)
            with open(tickets_model_path, 'rb') as f:
                tickets_model = pickle.load(f)
            with open(data_path, 'rb') as f:
                processed_data = pickle.load(f)
            
            print(f"Loaded cached models for data hash: {data_hash}")
            return revenue_model, tickets_model, processed_data
    except Exception as e:
        print(f"Warning: Error loading cached models: {e}")
    
    return None, None, None

def save_models_to_cache(revenue_model, tickets_model, processed_data, data_hash):
    """
    Save trained models and processed data to cache.
    """
    try:
        os.makedirs(MODELS_DIR, exist_ok=True)
        
        revenue_model_path = os.path.join(MODELS_DIR, f"revenue_model_{data_hash}.pkl")
        tickets_model_path = os.path.join(MODELS_DIR, f"tickets_model_{data_hash}.pkl")
        data_path = os.path.join(MODELS_DIR, f"processed_data_{data_hash}.pkl")
        
        with open(revenue_model_path, 'wb') as f:
            pickle.dump(revenue_model, f)
        with open(tickets_model_path, 'wb') as f:
            pickle.dump(tickets_model, f)
        with open(data_path, 'wb') as f:
            pickle.dump(processed_data, f)
        
        print(f"Saved models to cache for data hash: {data_hash}")
    except Exception as e:
        print(f"Warning: Error saving models to cache: {e}")

def predict_current_month():
    """
    Predict total_revenue and total_tickets for the current month.
    Loads data from revenue_data.json inside 'data' folder.
    Uses cached models if available, otherwise trains new models and caches them.
    Returns last 8 months including current month for dashboard plotting.
    """
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} not found.")

    with open(DATA_FILE) as f:
        data = json.load(f)

    if not data:
        raise ValueError("No data found in JSON file.")

    data_hash = get_data_hash(data)
    
    cached_revenue_model, cached_tickets_model, cached_processed_data = load_cached_models(data_hash)
    
    if cached_revenue_model is not None and cached_tickets_model is not None and cached_processed_data is not None:
        df = cached_processed_data['df']
        current_month = cached_processed_data['current_month']
        exog_vars = cached_processed_data['exog_vars']
        
        exog_current = df.loc[current_month, exog_vars].values.reshape(1, -1)
        
        pred_revenue = cached_revenue_model.forecast(steps=1, exog=exog_current).iloc[0]
        pred_tickets = cached_tickets_model.forecast(steps=1, exog=exog_current).iloc[0]
        
        df.loc[current_month, 'total_revenue'] = pred_revenue
        df.loc[current_month, 'total_tickets'] = pred_tickets
        
        print("Used cached models for prediction")
    else:
        print("Training new models...")
        
        df = pd.DataFrame(data)

        if 'month' not in df.columns:
            raise ValueError("The loaded data does not contain a 'month' column.")

        df['month'] = pd.to_datetime(df['month'])
        df = df.set_index('month').sort_index()

        df_train = df.iloc[-36:].copy()

        exog_vars = ['no_of_clients', 'churn_rate', 'inflation_rate', 'holiday_month', 'festival_count']

        for var in exog_vars:
            if var not in df.columns:
                df[var] = 0
            if var not in df_train.columns:
                df_train[var] = df[var].iloc[-36:]
        
        numeric_cols = ['total_revenue', 'total_tickets'] + exog_vars
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            if col in df_train.columns:
                df_train[col] = pd.to_numeric(df_train[col], errors='coerce')
        
        if 'holiday_month' in df.columns:
            df['holiday_month'] = df['holiday_month'].astype(int)
        if 'holiday_month' in df_train.columns:
            df_train['holiday_month'] = df_train['holiday_month'].astype(int)

        current_month = pd.Timestamp(datetime.today().strftime('%Y-%m-01'))

        if current_month not in df.index:
            last_row = df.iloc[-1].copy()
            new_row = last_row.copy()
            new_row.name = current_month
            df = pd.concat([df, pd.DataFrame([new_row])])

        sarimax_revenue = SARIMAX(
            df_train['total_revenue'],
            exog=df_train[exog_vars],
            order=(1,1,1),
            seasonal_order=(1,1,1,12)
        )
        sarimax_revenue_fit = sarimax_revenue.fit(disp=False)

        sarimax_tickets = SARIMAX(
            df_train['total_tickets'],
            exog=df_train[exog_vars],
            order=(1,1,1),
            seasonal_order=(1,1,1,12)
        )
        sarimax_tickets_fit = sarimax_tickets.fit(disp=False)

        exog_current = df.loc[current_month, exog_vars].values.reshape(1, -1)

        pred_revenue = sarimax_revenue_fit.forecast(steps=1, exog=exog_current).iloc[0]
        pred_tickets = sarimax_tickets_fit.forecast(steps=1, exog=exog_current).iloc[0]

        df.loc[current_month, 'total_revenue'] = pred_revenue
        df.loc[current_month, 'total_tickets'] = pred_tickets

        processed_data = {
            'df': df,
            'current_month': current_month,
            'exog_vars': exog_vars
        }
        save_models_to_cache(sarimax_revenue_fit, sarimax_tickets_fit, processed_data, data_hash)

    last_18 = df.iloc[-18:].reset_index()
    if 'month' not in last_18.columns:
        last_18.rename(columns={last_18.columns[0]: 'month'}, inplace=True)
    last_18['month'] = pd.to_datetime(last_18['month']).dt.strftime('%Y-%m')
    
    result = []
    for _, row in last_18.iterrows():
        result.append({
            'month': row['month'],
            'revenue': round(float(row['total_revenue']), 2),
            'tickets': round(float(row['total_tickets']), 0)
        })

    return result
