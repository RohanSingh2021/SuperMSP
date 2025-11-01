

import re
import threading
import sqlite3
from pathlib import Path
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv

load_dotenv()

llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")

DATABASE_PATH = Path(__file__).parent.parent / "databases" / "msp_data.db"

db_lock = threading.Lock()

def load_technicians():
    """Load technicians from database safely with a lock."""
    with db_lock:
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row  
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    technician_id,
                    name,
                    email,
                    specialization,
                    tickets_assigned,
                    active_status,
                    created_at,
                    pending_ticket_count,
                    account_id
                FROM technicians
                WHERE active_status = 1
                ORDER BY name
            """)
            
            technicians = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return technicians
        except sqlite3.Error as e:
            print(f"Database error loading technicians: {e}")
            return []

def update_technician_in_db(technician_id, tickets_assigned, pending_ticket_count):
    """Update technician's ticket counts in the database."""
    with db_lock:
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE technicians 
                SET tickets_assigned = ?, pending_ticket_count = ? 
                WHERE technician_id = ?
            """, (tickets_assigned, pending_ticket_count, technician_id))
            
            conn.commit()
            conn.close()
            print(f"Updated technician {technician_id} in database with {tickets_assigned} assigned tickets and {pending_ticket_count} pending tickets")
            return True
        except sqlite3.Error as e:
            print(f"Database error updating technician {technician_id}: {e}")
            return False
        except Exception as e:
            print(f"Error updating technician {technician_id}: {e}")
            return False


CATEGORIES = [
    "Network & Connectivity Support",
    "Email & Collaboration Tools Support", 
    "Hardware Maintenance & Repair",
    "Software Installation & Configuration",
    "Security & Malware Response",
    "Access Control & Permissions",
    "VPN & Remote Access Support",
    "Printer & Peripheral Support",
    "Account & Password Management",
    "Application Performance Troubleshooting",
    "New User Onboarding",
    "General IT Consultation"
]


def classify_ticket_llm(ticket: dict) -> str:
    """
    Classify a ticket into one of the 10 categories using LLM.
    Returns the category string.
    """
    ticket_text = f"Title: {ticket.get('title','')}\nDescription: {ticket.get('description','')}"
    prompt = f"""
    You are an IT service desk assistant. Classify the ticket below into ONE of the following 10 categories:

    Categories: {', '.join(CATEGORIES)}

    Ticket:
    {ticket_text}

    Reply ONLY with the category name (no explanations).
    """
    response = llm.invoke(prompt).content.strip()

    if response not in CATEGORIES:
        print(f"Classified ticket as: General IT Consultation")
        return "General IT Consultation"
    print(f"Classified ticket as: {response}")
    return response

def assign_ticket_llm(ticket: dict):
    """Assign a ticket to a suitable technician with thread-safe database access."""
    technicians = load_technicians() 
    ticket_category = classify_ticket_llm(ticket)

    suitable = [
        tech for tech in technicians
        if ticket_category in tech["specialization"]
        and tech["pending_ticket_count"] < 150
    ]

    if not suitable:
        return None  

    assigned_tech = min(suitable, key=lambda x: x["pending_ticket_count"])
    assigned_tech["tickets_assigned"] += 1
    assigned_tech["pending_ticket_count"] += 1

    success = update_technician_in_db(assigned_tech["technician_id"], assigned_tech["tickets_assigned"], assigned_tech["pending_ticket_count"])
    
    if success:
        return assigned_tech
    else:
        assigned_tech["tickets_assigned"] -= 1
        assigned_tech["pending_ticket_count"] -= 1
        return None
