

import json
import re
import os
from pathlib import Path
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv

load_dotenv()

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")



DATA_DIR = Path(__file__).parent.parent / "data"
SLA_FILE = DATA_DIR / "sla_sample.txt"


def load_sla_text():
    """Load SLA text from file."""
    if not SLA_FILE.exists():
        raise FileNotFoundError(f"SLA file not found: {SLA_FILE}")
    return SLA_FILE.read_text(encoding="utf-8")

def parse_llm_json(text: str) -> dict:
    """
    Extract and parse JSON from LLM response, even if it's wrapped in markdown code fences.
    """
    try:
        cleaned = re.sub(r"```(json)?", "", text).strip().strip("`")
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "covered": False,
            "explanation": text,
            "relevant_section": None
        }

llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")

def check_sla_with_llm(ticket: dict) -> str:
    """
    Use SLA content and LLM to check if ticket is covered.
    Returns raw string response from LLM (may include markdown).
    """
    sla_text = load_sla_text()
    ticket_text = ticket.get("title", "") + " " + ticket.get("description", "")

    prompt_text = f"""
You are a service desk assistant. Check if the ticket below is covered under the SLA.
If a service is mentioned in the SLA but no explicit service level metric or guarantee is defined for the specific issue (e.g., performance degradation vs. availability), return covered: false.
Use ONLY the SLA content provided. Reply STRICTLY in JSON format, no extra text.

Ticket:
{ticket_text}

SLA Content:
{sla_text}

Output JSON format:
{{
  "covered": true/false,
  "explanation": "Reason why ticket is or isn't covered",
  "relevant_section": "The SLA section(s) supporting your answer"
}}
"""
    return llm.invoke(prompt_text).content.strip()


def check_sla(ticket: dict) -> dict:
    """
    Check SLA coverage for a ticket and return a clean Python dictionary:
    {
      "covered": bool,
      "explanation": str,
      "relevant_section": str or None
    }
    """
    try:
        raw_response = check_sla_with_llm(ticket)
        return parse_llm_json(raw_response)
    except Exception as e:
        print("Error checking SLA:", e)
        return {
            "covered": False,
            "explanation": str(e),
            "relevant_section": None
        }
