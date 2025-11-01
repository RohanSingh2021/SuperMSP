import pandas as pd
from langchain.schema import HumanMessage
from .llm_wrapper import llm

def summarize_result(user_query: str, df_result: pd.DataFrame) -> str:
    """
    Summarizes the result DataFrame in natural language for the user.
    """
    if df_result.empty:
        return "Warning: No matching records found for your query."

    all_records = df_result.to_dict(orient="records")

    prompt = f"""
You are an assistant that explains tabular data from a Managed Service Provider (MSP) system.

User question:
"{user_query}"

Here are all the records from the result:
{all_records}

Write a brief, professional summary describing the key insight. Include ALL records in your response - do not truncate or limit the list.
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip()
