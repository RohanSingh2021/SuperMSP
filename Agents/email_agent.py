import os
import json
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your-email@example.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your-app-password")

OUTPUT_DIR = Path("output")
DB_PATH = Path("databases/msp_data.db")


def run_financial_computation():
    """
    Import and run the financial computation function to generate JSON files.
    """
    try:
        from src.computations.financial_data_generator import run_financial_computation as compute
        compute()
        return True
    except Exception as e:
        print(f"Error running financial computation: {e}")
        return False


def load_overdue_payments() -> List[Dict]:
    """Load overdue payments from JSON file."""
    file_path = OUTPUT_DIR / "overdue_payments.json"
    if not file_path.exists():
        return []
    
    with open(file_path, 'r') as f:
        data = json.load(f)
        return data if isinstance(data, list) else []


def load_upcoming_payments(days: int = 7) -> List[Dict]:
    """Load upcoming payments within specified days."""
    file_path = OUTPUT_DIR / "upcoming_due_dates.json"
    if not file_path.exists():
        return []
    
    with open(file_path, 'r') as f:
        data = json.load(f)
        payments = data if isinstance(data, list) else []
        
    return [p for p in payments if p.get('days_until_due', 0) <= days]


def get_technician_email(name: str) -> Optional[str]:
    """Get technician email from database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT email FROM technicians WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{name}%",)
        )
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        print(f"Database error: {e}")
        return None


def get_all_technicians() -> List[Dict]:
    """Get all technicians from database for suggestions."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name, email, specialization FROM technicians")
        results = cursor.fetchall()
        conn.close()
        
        return [
            {"name": row[0], "email": row[1], "specialization": row[2]}
            for row in results
        ]
    except Exception as e:
        print(f"Database error: {e}")
        return []


def create_overdue_payment_email(payment: Dict) -> Dict:
    """Create email content for overdue payment."""
    subject = f"Payment Reminder: Invoice Overdue - {payment.get('company_name', 'N/A')}"
    
    body = f"""Dear {payment.get('company_name', 'Valued Client')},

This is a friendly reminder that your invoice is currently overdue.

Invoice Details:
- Company: {payment.get('company_name', 'N/A')}
- Amount Due: ${payment.get('amount_due', 0):,.2f}
- Original Due Date: {payment.get('due_date', 'N/A')}
- Days Overdue: {payment.get('days_overdue', 0)}

Please arrange payment at your earliest convenience. If you have already made this payment, please disregard this notice.

For any questions, please reply to this mail.

Best regards,
MSP Financial Team
"""
    
    return {
        "to": payment.get('contact_email'),
        "subject": subject,
        "body": body,
        "company": payment.get('company_name')
    }


def create_upcoming_payment_email(payment: Dict) -> Dict:
    """Create email content for upcoming payment."""
    subject = f"Payment Due Soon: {payment.get('company_name', 'N/A')}"
    
    body = f"""Dear {payment.get('company_name', 'Valued Client')},

This is a reminder that you have an upcoming payment due.

Invoice Details:
- Company: {payment.get('company_name', 'N/A')}
- Amount Due: ${payment.get('amount_due', 0):,.2f}
- Due Date: {payment.get('due_date', 'N/A')}
- Days Until Due: {payment.get('days_until_due', 0)}

Please ensure payment is made by the due date to avoid any late fees.

For any questions, please reply to this mail.

Best regards,
MSP Financial Team
"""
    
    return {
        "to": payment.get('contact_email'),
        "subject": subject,
        "body": body,
        "company": payment.get('company_name')
    }


def create_technician_email(email: str, name: str, message: str) -> Dict:
    """Create email content for technician."""
    subject = f"Message from Management"
    
    body = f"""Dear {name},

{message}

Best regards,
Management Team
"""
    
    return {
        "to": email,
        "subject": subject,
        "body": body,
        "recipient": name
    }


def handle_email_command(command: str, args: List[str]) -> Dict:
    """
    Handle email slash commands and return preview data for approval.
    
    Args:
        command: The email command (overdue-payments, upcoming-payments, technician)
        args: Additional arguments for the command
    
    Returns:
        Dict with status, email previews, and metadata
    """
    
    if command == "overdue-payments":
        if not (OUTPUT_DIR / "overdue_payments.json").exists():
            run_financial_computation()
        
        payments = load_overdue_payments()
        
        if not payments:
            return {
                "status": "no_data",
                "message": "No overdue payments found."
            }
        
        emails = [create_overdue_payment_email(p) for p in payments]
        
        return {
            "status": "pending_approval",
            "command": "overdue-payments",
            "email_count": len(emails),
            "emails": emails,
            "message": f"Found {len(emails)} overdue payment(s). Review and approve to send."
        }
    
    elif command == "upcoming-payments":
        days = int(args[0]) if args and args[0].isdigit() else 7
        
        if not (OUTPUT_DIR / "upcoming_due_dates.json").exists():
            run_financial_computation()
        
        payments = load_upcoming_payments(days)
        
        if not payments:
            return {
                "status": "no_data",
                "message": f"No payments due within {days} days."
            }
        
        emails = [create_upcoming_payment_email(p) for p in payments]
        
        return {
            "status": "pending_approval",
            "command": "upcoming-payments",
            "email_count": len(emails),
            "emails": emails,
            "message": f"Found {len(emails)} payment(s) due within {days} days. Review and approve to send."
        }
    
    elif command == "technician":
        if len(args) < 2:
            return {
                "status": "error",
                "message": "Usage: /email-technician [name] [message]\nExample: /email-technician John Please review ticket #123"
            }
        
        name = args[0]
        message = " ".join(args[1:])
        
        email = get_technician_email(name)
        
        if not email:
            all_techs = get_all_technicians()
            suggestions = "\n".join([f"- {t['name']} ({t['specialization']})" for t in all_techs])
            
            return {
                "status": "error",
                "message": f"Technician '{name}' not found.\n\nAvailable technicians:\n{suggestions}"
            }
        
        email_data = create_technician_email(email, name, message)
        
        return {
            "status": "pending_approval",
            "command": "technician",
            "email_count": 1,
            "emails": [email_data],
            "message": f"Email ready for {name}. Review and approve to send."
        }
    
    else:
        return {
            "status": "error",
            "message": f"Unknown email command: {command}"
        }


def send_emails(emails: List[Dict]) -> Dict:
    """
    Actually send the emails using SMTP.
    
    Args:
        emails: List of email dictionaries with 'to', 'subject', 'body'
    
    Returns:
        Dict with success status and details
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import signal
    import time
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
    
    def send_emails_worker():
        """Worker function that performs the actual email sending"""
        sent_count = 0
        failed = []
        server = None
        
        try:
            if SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30)
            else:
                server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
                server.starttls()
            
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            
            for email_data in emails:
                try:
                    msg = MIMEMultipart()
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = email_data['to']
                    msg['Subject'] = email_data['subject']
                    msg.attach(MIMEText(email_data['body'], 'plain'))
                    
                    server.send_message(msg)
                    sent_count += 1
                    
                except Exception as e:
                    failed.append({
                        "to": email_data['to'],
                        "error": str(e)
                    })
            
            if server:
                server.quit()
            
            return {
                "status": "sent",
                "sent_count": sent_count,
                "failed_count": len(failed),
                "failed": failed,
                "message": f"Successfully sent {sent_count}/{len(emails)} email(s)."
            }
            
        except Exception as e:
            if server:
                try:
                    server.quit()
                except:
                    pass
            return {
                "status": "error",
                "message": f"Failed to connect to email server: {str(e)}"
            }
    
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(send_emails_worker)
            
            try:
                result = future.result(timeout=120)
                return result
                
            except FutureTimeoutError:
                future.cancel()
                return {
                    "status": "timeout",
                    "message": "Email sending process timed out after 120 seconds. The operation has been aborted. You can continue chatting normally.",
                    "sent_count": 0,
                    "failed_count": len(emails),
                    "timeout_duration": 120
                }
                
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error during email sending process: {str(e)}"
        }


def get_help_text() -> str:
    """Return help text for all slash commands."""
    return """Available Chatbot Commands
(Use `/` before each command — e.g., `/email-overdue-payments`)

------------------------------------------------------------
Payment Reminder Commands

/email-overdue-payments
→ Sends payment reminder emails to all companies with overdue invoices.
You'll receive a preview of the recipients and content before the emails are sent.

------------------------------------------------------------
Upcoming Payment Notifications

/email-upcoming-payments [days]
→ Notifies companies about payments due within the next X days.
If [days] is not specified, the default is 7 days.
Example: /email-upcoming-payments 14

------------------------------------------------------------
Technician Communication

/email-technician [technician_name] [message]
→ Sends a custom message directly to a specific technician.
Example: /email-technician John Please review ticket #456

------------------------------------------------------------
Important Note

All outgoing emails require manual approval before sending.
You'll see a preview showing recipients and message content for confirmation.

------------------------------------------------------------
File Export Commands

/pdf <query>
→ Exports your current analysis, summary, or report as a PDF file.
Example: /pdf monthly payment summary

------------------------------------------------------------
Tip:
Type /help anytime to revisit this list."""
