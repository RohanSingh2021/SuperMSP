from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import sqlite3
from typing import List, Dict, Any, Optional
import json
from agents import sla_agent, rag_agent, human_approval, scheduler, technician_agent
from software_recommendation import get_software_recommendations 
from negotiation_orchestrator import compare_multiple_quotations
from chatbot_orchestrator import run_orchestrator
from src.computations.financial_data_generator import run_financial_computation
from prediction import predict_current_month
import re
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import uuid
import shutil
from chatbot_orchestrator import run_orchestrator, handle_email_approval


import main

from websocket_manager import websocket_manager

from negotiation_orchestrator import NegotiationsAgent, UPLOADS_FOLDER, RESULTS_FOLDER, GEMINI_API_KEY

from agents.search_agent import (
    graph
)

DATABASE_PATH = "./databases/msp_data.db"



app = FastAPI(
    title="IT Contacts Suggestion API",
    description="Fetch best IT contacts for companies based on requirement",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequirementRequest(BaseModel):
    requirement: str

class ContactResponse(BaseModel):
    company: str
    name: str
    title: str
    linkedin: str

class SoftwareRequest(BaseModel):
    requirement: str

class UserMessage(BaseModel):
    message: str

class AnalysisStatus(BaseModel):
    status: str
    message: str
    progress: Optional[str] = None
    results: Optional[Dict[str, Any]] = None

class UploadResponse(BaseModel):
    message: str
    files_uploaded: List[str]
    analysis_result: Optional[Dict[str, Any]] = None

class DashboardMetrics(BaseModel):
    total_revenue: float
    pending_revenue: float
    overdue_revenue: float
    customer_satisfaction: float
    tickets_resolved: int

class CriticalAlerts(BaseModel):
    amount_overdue: float
    low_satisfaction_customers: int
    licenses_expiring_2025: int

class CompanyContract(BaseModel):
    company_id: int
    company_name: str
    contract_status: str
    total_tickets: int
    annual_revenue: float

class UserMessage(BaseModel):
    message: str

class EmailApproval(BaseModel):
    approved: bool
    emails: List[Dict[str, Any]]
    command: str

pending_approvals = {}

analysis_status = {
    "status": "idle",
    "message": "Ready to process files",
    "progress": None,
    "results": None
}



def clear_uploads_folder():
    """Clear the uploads folder before new upload"""
    if os.path.exists(UPLOADS_FOLDER):
        shutil.rmtree(UPLOADS_FOLDER)
    os.makedirs(UPLOADS_FOLDER, exist_ok=True)

def save_uploaded_files(files: List[UploadFile]) -> List[str]:
    """Save uploaded files to the uploads folder"""
    saved_files = []
    
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            print(f"Warning: Skipping non-PDF file: {file.filename}")
            continue
            
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        file_path = os.path.join(UPLOADS_FOLDER, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        saved_files.append(unique_filename)
        print(f"Saved: {unique_filename}")
    
    return saved_files

def run_negotiation_analysis():
    """Run the negotiation analysis in background"""
    global analysis_status
    
    try:
        analysis_status["status"] = "processing"
        analysis_status["message"] = "Starting negotiation analysis..."
        analysis_status["progress"] = "Initializing agent..."
        
        if not GEMINI_API_KEY:
            raise Exception("GEMINI_API_KEY not found in environment variables")
        
        agent = NegotiationsAgent(api_key=GEMINI_API_KEY)
        
        analysis_status["progress"] = "Loading documents..."
        
        final_state = agent.run()
        
        concise_report_path = os.path.join(RESULTS_FOLDER, "concise_report.json")
        negotiation_report_path = os.path.join(RESULTS_FOLDER, "negotiation_report.json")
        
        results = {}
        
        if os.path.exists(concise_report_path):
            with open(concise_report_path, 'r', encoding='utf-8') as f:
                results["concise_report"] = json.load(f)
        
        if os.path.exists(negotiation_report_path):
            with open(negotiation_report_path, 'r', encoding='utf-8') as f:
                full_report = json.load(f)
                results["metadata"] = full_report.get("metadata", {})
                results["quotations_analyzed"] = full_report["metadata"].get("quotations_analyzed", 0)
        
        analysis_status["status"] = "completed"
        analysis_status["message"] = "Analysis completed successfully"
        analysis_status["progress"] = "Done"
        analysis_status["results"] = results
        
    except Exception as e:
        analysis_status["status"] = "error"
        analysis_status["message"] = f"Analysis failed: {str(e)}"
        analysis_status["progress"] = "Error occurred"
        analysis_status["results"] = None

@app.websocket("/ws/tickets")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time ticket updates
    """
    client_id = f"dashboard_{datetime.now().timestamp()}"
    
    try:
        await websocket_manager.connect(websocket, client_id)
        print(f"WebSocket client connected: {client_id}")
        
        timeline = main.get_processing_timeline()
        pending_tickets = main.get_pending_approval_tickets()
        
        await websocket_manager.send_personal_message({
            "type": "initial_data",
            "timeline": timeline,
            "pending_tickets": pending_tickets
        }, websocket)
        print(f"Sent initial data to {client_id}: {len(timeline)} timeline entries, {len(pending_tickets)} pending tickets")
        
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                print(f"Received message from {client_id}: {message.get('type', 'unknown')}")
                await websocket_manager.handle_client_message(websocket, message)
            except WebSocketDisconnect:
                print(f"WebSocket client disconnected: {client_id}")
                break
            except json.JSONDecodeError:
                print(f"Invalid JSON from {client_id}")
                await websocket_manager.send_personal_message({
                    "type": "error",
                    "message": "Invalid JSON format"
                }, websocket)
            except Exception as e:
                print(f"Error processing message from {client_id}: {e}")
                await websocket_manager.send_personal_message({
                    "type": "error",
                    "message": f"Error processing message: {str(e)}"
                }, websocket)
                
    except WebSocketDisconnect:
        print(f"WebSocket client disconnected during setup: {client_id}")
        pass
    except Exception as e:
        print(f"WebSocket error for {client_id}: {e}")
    finally:
        websocket_manager.disconnect(websocket)
        print(f"🧹 Cleaned up WebSocket connection: {client_id}")

@app.get("/api/websocket/info")
def get_websocket_info():
    """
    Get information about active WebSocket connections
    """
    return {
        "active_connections": websocket_manager.get_connection_count(),
        "connections": websocket_manager.get_connection_info()
    }


@app.post("/api/agent/people/suggest", response_model=List[ContactResponse])
def suggest_people(request: RequirementRequest):
    """
    Given a requirement string, returns best IT contacts for companies.
    """
    if not request.requirement:
        raise HTTPException(status_code=400, detail="Requirement is required.")

    initial_state = {
        "query": request.requirement,
        "location": None,
        "companies": [],
        "enriched_companies": []
    }

    final_state = graph.invoke(initial_state)

    contacts: List[Dict[str, Any]] = final_state.get("enriched_companies", [])

    return contacts

@app.get("/api/clients/allClients")
def get_clients():
    """
    Returns a list of all clients (company names) for the overview page.
    """
    try:
        with sqlite3.connect("databases/msp_data.db", timeout=30.0) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT company_id, company_name, happiness_score FROM companies ORDER BY company_name ASC")
            rows = cursor.fetchall()
            
            clients = [{"company_id": row[0], "company_name": row[1], "happiness_score": float(row[2]) if row[2] is not None else 0.0} for row in rows]
            
            return clients
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/clients/{company_id}/softwares")
def get_company_softwares(company_id: int):
    """
    Returns aggregated software info for a given company:
    - software name
    - license type
    - number of customer company employees using it
    """
    try:
        with sqlite3.connect("databases/msp_data.db", timeout=30.0) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT assigned_software FROM customer_company_employees WHERE company_id = ?",
                (company_id,)
            )
            rows = cursor.fetchall()
            if not rows:
                return []

            software_count = defaultdict(lambda: {"license_type": "", "count": 0})

            for row in rows:
                assigned_software_json = row[0]
                if not assigned_software_json:
                    continue

                try:
                    software_list = json.loads(assigned_software_json)
                except json.JSONDecodeError:
                    continue

                for software in software_list:
                    key = software["name"]
                    software_count[key]["license_type"] = software.get("license_type", "")
                    software_count[key]["count"] += 1

            result = [
                {"name": name, "license_type": data["license_type"], "count": data["count"]}
                for name, data in software_count.items()
            ]

            return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/clients/{company_id}/tickets")
def get_company_tickets(company_id: int):
    """
    Returns all tickets for a given company ordered by created_at:
    - title
    - status (Open/Closed)
    """
    try:
        with sqlite3.connect("databases/msp_data.db", timeout=30.0) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT ticket_id, title, status, priority
                FROM tickets
                WHERE company_id = ?
                ORDER BY datetime(created_at) ASC
            """, (company_id,))

            rows = cursor.fetchall()

            result = [{"ticket_id": row[0], "title": row[1], "status": row[2], "priority":row[3]} for row in rows]
            print(f"Fetched {result} tickets for company_id {company_id}")
            return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/clients/{company_id}/billing-summary")
def get_company_billing_summary(company_id: int):
    try:
        with sqlite3.connect("databases/msp_data.db", timeout=30.0) as conn:
            cursor = conn.cursor()

            current_year = datetime.utcnow().year

            cursor.execute("""
                SELECT amount_due, amount_paid, due_date, payment_date, status
                FROM payments
                WHERE company_id = ?
            """, (company_id,))
            rows = cursor.fetchall()

            if not rows:
                return {
                    "total_billed": 0,
                    "outstanding_balance": 0,
                    "last_payment": "No payments yet",
                    "next_billing": "No upcoming bills"
                }

            total_billed = 0
            outstanding_balance = 0
            last_payment_date = None
            next_billing_date = None

            for amount_due, amount_paid, due_date, payment_date, status in rows:
                due_dt = datetime.strptime(due_date, "%Y-%m-%d") if due_date else None
                pay_dt = datetime.strptime(payment_date, "%Y-%m-%d") if payment_date else None

                if due_dt and due_dt.year == current_year:
                    total_billed += amount_due

                if amount_paid < amount_due:
                    outstanding_balance += (amount_due - amount_paid)

                if pay_dt and (last_payment_date is None or pay_dt > last_payment_date):
                    last_payment_date = pay_dt

                if status == "Pending" and due_dt and due_dt.date() >= datetime.utcnow().date():
                    if next_billing_date is None or due_dt.date() < next_billing_date:
                        next_billing_date = due_dt.date()

            print(
                f"Billing summary for company_id {company_id}: "
                f"Total Billed={total_billed}, Outstanding={outstanding_balance}, "
                f"Last Payment={last_payment_date}, Next Billing={next_billing_date}"
            )

            return {
                "total_billed": total_billed,
                "outstanding_balance": outstanding_balance,
                "last_payment": last_payment_date.strftime("%Y-%m-%d") if last_payment_date else "No payments yet",
                "next_billing": next_billing_date.strftime("%Y-%m-%d") if next_billing_date else "No upcoming bills"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/clients/stats")
def get_client_stats():
    """
    Returns overall stats:
    - average_happiness_score
    - total_tickets_raised
    """
    try:
        with sqlite3.connect("databases/msp_data.db", timeout=30.0) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT AVG(happiness_score) FROM companies")
            avg_happiness = cursor.fetchone()[0] or 0

            cursor.execute("SELECT SUM(tickets_raised) FROM companies")
            total_tickets = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM company_contract WHERE contract_status = 'Active'")
            active_companies = cursor.fetchone()[0] or 0

            return {
                "average_happiness_score": round(avg_happiness, 2),
                "total_tickets_raised": total_tickets,
                "active_companies_count": active_companies
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/agent/upload")
def upload_files(files: List[UploadFile] = File(...)):
    """
    Accept multiple PDF files, save temporarily, run negotiation analysis,
    and return JSON result with proper status updates.
    """
    global analysis_status
    
    print("Received files:", [file.filename for file in files])
    
    try:
        if not files:
            return JSONResponse(content={"error": "No files uploaded"}, status_code=400)

        clear_uploads_folder()
        saved_files = save_uploaded_files(files)

        if not saved_files:
            return JSONResponse(content={"error": "No PDF files uploaded"}, status_code=400)

        print(f"Saved {len(saved_files)} files to {UPLOADS_FOLDER}")

        analysis_status = {
            "status": "processing",
            "message": "The Negotiation Agent is working on several steps right now. Sit tight — it might take a little while to finish everything!",
            "progress": "Initializing...",
            "results": None
        }

        result = compare_multiple_quotations(pdf_dir=UPLOADS_FOLDER)
        
        if result.get("status") == "success":
            analysis_status = {
                "status": "completed",
                "message": "Analysis completed successfully",
                "progress": "Done",
                "results": result
            }
            
            if "concise_report" in result:
                print("\n" + "="*80)
                print("CONCISE REPORT GENERATED:")
                print("="*80)
                print(json.dumps(result["concise_report"], indent=2))
                print("="*80 + "\n")
        else:
            analysis_status = {
                "status": "error",
                "message": result.get("error", "Analysis failed"),
                "progress": "Error",
                "results": None
            }

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        print("Error processing negotiation:", e)
        analysis_status = {
            "status": "error",
            "message": f"Analysis failed: {str(e)}",
            "progress": "Error",
            "results": None
        }
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
@app.get("/api/clients/{company_id}/alerts")
def get_client_alerts(company_id: int):
    try:
        with sqlite3.connect("databases/msp_data.db", timeout=30.0) as conn:
            cursor = conn.cursor()

            alerts = []

            cursor.execute("""
                SELECT payment_id, amount_due, amount_paid, due_date, status
                FROM payments
                WHERE company_id = ?
            """, (company_id,))
            payments = cursor.fetchall()
            today = datetime.utcnow().date()

            for payment_id, amount_due, amount_paid, due_date, status in payments:
                due_dt = datetime.strptime(due_date, "%Y-%m-%d").date() if due_date else None

                if status == "Overdue" or (due_dt and due_dt < today and amount_paid < amount_due):
                    alerts.append({
                        "type": "payment",
                        "color": "red",
                        "message": f"Overdue Payment: Invoice #{payment_id}, ${amount_due}"
                    })
                elif status == "Pending" and due_dt and 0 <= (due_dt - today).days <= 5:
                    alerts.append({
                        "type": "payment",
                        "color": "yellow",
                        "message": f"Upcoming Payment: Invoice #{payment_id}, ${amount_due} due in {(due_dt - today).days} days"
                    })

            one_month_ago = datetime.utcnow() - timedelta(days=30)
            cursor.execute("""
                SELECT log_id, employee_id, software_name, last_used, ttl
                FROM activity_logs
                WHERE company_id = ?
            """, (company_id,))
            activity_logs = cursor.fetchall()

            for log_id, employee_id, software_name, last_used, ttl in activity_logs:
                last_used_dt = datetime.strptime(last_used, "%Y-%m-%dT%H:%M:%S")
                if last_used_dt < one_month_ago:
                    alerts.append({
                        "type": "license",
                        "color": "orange",
                        "message": f"License '{software_name}' inactive for over a month"
                    })

            return alerts

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/chatbot/respond")
def chatbot_respond(user_msg: UserMessage):
    """
    Main chatbot endpoint that handles both regular queries and slash commands.
    """
    try:
        query = user_msg.message.strip()
        if not query:
            return JSONResponse(content={"error": "Empty message"}, status_code=400)

        bot_response = run_orchestrator(query, verbose=False)
        
        if isinstance(bot_response, dict) and bot_response.get("type") == "email":
            if bot_response.get("status") == "pending_approval":
                import uuid
                approval_id = str(uuid.uuid4())
                pending_approvals[approval_id] = {
                    "emails": bot_response["emails"],
                    "command": bot_response["command"]
                }
                
                bot_response["approval_id"] = approval_id
                bot_response["requires_approval"] = True
        
        return JSONResponse(content=bot_response, status_code=200)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/api/chatbot/approve-email")
def approve_email_send(approval: EmailApproval):
    """
    Endpoint to handle email approval/rejection.
    Handles timeout scenarios gracefully to allow continued chatting.
    """
    try:
        if not approval.approved:
            return JSONResponse(content={
                "status": "cancelled",
                "message": "Email sending cancelled by user."
            }, status_code=200)
        
        result = handle_email_approval({
            "approved": True,
            "emails": approval.emails
        })
        
        if result.get("status") == "timeout":
            return JSONResponse(content={
                "status": "timeout",
                "message": result.get("message", "Email sending timed out after 120 seconds."),
                "timeout_duration": result.get("timeout_duration", 120),
                "can_continue_chat": True
            }, status_code=200)
        
        return JSONResponse(content=result, status_code=200)
    
    except Exception as e:
        return JSONResponse(content={
            "status": "error",
            "message": f"Error sending emails: {str(e)}",
            "can_continue_chat": True
        }, status_code=500)



    
@app.post("/api/agent/software/recommend", response_model=Dict)
def software_recommend(request: SoftwareRequest):
    if not request.requirement.strip():
        raise HTTPException(status_code=400, detail="Requirement is required")
    
    result = get_software_recommendations(request.requirement)
    return result



@app.get("/api/price-revision/{company_id}")
def get_price_revision(company_id: int):
    """
    Returns the revised pricing details for a given company.
    If the computation file doesn't exist, it generates it first.
    """
    output_file = Path("output/price_revisions.json")

    if not output_file.exists():
        try:
            print("Running financial computation...")
            run_financial_computation()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating price revisions: {str(e)}")

    try:
        with open(output_file, "r", encoding="utf-8") as f:
            price_revisions = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading price revisions file: {str(e)}")

    company_data = next((item for item in price_revisions if item["company_id"] == company_id), None)
    if not company_data:
        raise HTTPException(status_code=404, detail=f"No price revision data found for company_id {company_id}")

    result = {
        "revision_percentage": company_data["revision_percentage"],
        "revised_monthly_cost": company_data["revised_monthly_cost"],
        "annual_cost_change": company_data["annual_cost_change"]
    }

    return result

@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "gemini_api_configured": bool(GEMINI_API_KEY)
    }

@app.post("/api/agent/upload_and_analyze", response_model=UploadResponse)
def upload_and_analyze(files: List[UploadFile] = File(...)):
    """
    Upload files and run negotiation analysis synchronously
    """
    global analysis_status
    
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file type: {file.filename}. Only PDF files are supported."
                )
        
        clear_uploads_folder()
        
        saved_files = save_uploaded_files(files)
        
        analysis_status = {
            "status": "processing",
            "message": f"Files uploaded successfully. Starting analysis for {len(saved_files)} files.",
            "progress": "Processing",
            "results": None
        }
        
        run_negotiation_analysis()
        
        return UploadResponse(
            message=f"Successfully uploaded and analyzed {len(saved_files)} files.",
            files_uploaded=saved_files,
            analysis_result=analysis_status.get("results", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload and analysis failed: {str(e)}")

@app.get("/api/agent/status", response_model=AnalysisStatus)
def get_analysis_status():
    """
    Get the current status of the analysis
    """
    return AnalysisStatus(**analysis_status)

@app.get("/api/agent/results")
def get_analysis_results():
    """
    Get the detailed analysis results
    """
    if analysis_status["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Analysis not completed. Current status: {analysis_status['status']}"
        )
    
    if not analysis_status["results"]:
        raise HTTPException(status_code=404, detail="No results available")
    
    return analysis_status["results"]

@app.get("/api/agent/results/concise")
def get_concise_results():
    """
    Get only the concise report results
    """
    if analysis_status["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Analysis not completed. Current status: {analysis_status['status']}"
        )
    
    if not analysis_status["results"] or "concise_report" not in analysis_status["results"]:
        raise HTTPException(status_code=404, detail="Concise report not available")
    
    return analysis_status["results"]["concise_report"]

@app.post("/api/agent/reset")
def reset_analysis():
    """
    Reset the analysis status and clear files
    """
    global analysis_status
    
    if os.path.exists(UPLOADS_FOLDER):
        shutil.rmtree(UPLOADS_FOLDER)
    os.makedirs(UPLOADS_FOLDER, exist_ok=True)
    
    analysis_status = {
        "status": "idle",
        "message": "Ready to process files",
        "progress": None,
        "results": None
    }
    
    return {"message": "Analysis reset successfully"}

@app.get("/api/agent/files")
def list_uploaded_files():
    """
    List currently uploaded files
    """
    if not os.path.exists(UPLOADS_FOLDER):
        return {"files": []}
    
    files = []
    for file_path in Path(UPLOADS_FOLDER).iterdir():
        if file_path.is_file():
            files.append({
                "name": file_path.name,
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            })
    
    return {"files": files}


@app.get("/api/dashboard/metrics", response_model=DashboardMetrics)
def get_dashboard_metrics() -> Dict:
    """
    Get dashboard metrics:
    - Total Revenue: Sum of paid amounts from payments table where status is 'Paid'
    - Pending Revenue: Sum of unpaid amounts (amount_due - amount_paid) from payments table where status is 'Pending'
    - Customer Satisfaction: Average happiness_score from companies table (as percentage)
    - Tickets Resolved: Sum of tickets_raised from companies table
    """
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COALESCE(SUM(amount_paid), 0) as total_revenue
                FROM payments
                WHERE status = 'Paid'
            """)
            total_revenue = cursor.fetchone()["total_revenue"]
            
            cursor.execute("""
                SELECT COALESCE(SUM(amount_due - amount_paid), 0) as pending_revenue
                FROM payments
                WHERE status = 'Pending' AND amount_due > amount_paid
            """)
            pending_revenue = cursor.fetchone()["pending_revenue"]
            
            cursor.execute("""
                SELECT COALESCE(SUM(amount_due - amount_paid), 0) as overdue_revenue
                FROM payments
                WHERE status = 'Overdue' AND amount_due > amount_paid
            """)
            overdue_revenue = cursor.fetchone()["overdue_revenue"]
            
            cursor.execute("""
                SELECT COALESCE(AVG(happiness_score), 0) as avg_satisfaction
                FROM companies
                WHERE happiness_score IS NOT NULL
            """)
            avg_satisfaction = cursor.fetchone()["avg_satisfaction"]
            customer_satisfaction = round(avg_satisfaction if avg_satisfaction > 1 else avg_satisfaction * 100, 2)
            
            cursor.execute("""
                SELECT COALESCE(SUM(tickets_raised), 0) as total_tickets
                FROM companies
                WHERE tickets_raised IS NOT NULL
            """)
            tickets_resolved = cursor.fetchone()["total_tickets"]
            
            return {
                "total_revenue": round(total_revenue, 2),
                "pending_revenue": round(pending_revenue, 2),
                "overdue_revenue": round(overdue_revenue, 2),
                "customer_satisfaction": customer_satisfaction,
                "tickets_resolved": int(tickets_resolved)
            }
            
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/dashboard/critical-alerts", response_model=CriticalAlerts)
def get_critical_alerts() -> Dict:
    """
    Get critical alerts:
    - Amount Overdue: Sum of (amount_due - amount_paid) from payments where status is not 'Paid'
    - Low Satisfaction Customers: Count of companies with happiness_score < 3
    - Licenses Expiring in 2025: Count of software licenses expiring in 2025
    """
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COALESCE(SUM(amount_due - amount_paid), 0) as amount_overdue
                FROM payments
                WHERE status == 'Overdue' 
            """)
            amount_overdue = cursor.fetchone()["amount_overdue"]
            
            cursor.execute("""
                SELECT COUNT(*) as low_satisfaction_count
                FROM companies
                WHERE happiness_score < 3 AND happiness_score IS NOT NULL
            """)
            low_satisfaction_customers = cursor.fetchone()["low_satisfaction_count"]
            
            cursor.execute("""
                SELECT COUNT(*) as expiring_licenses
                FROM software_inventory
                WHERE license_expiry IS NOT NULL 
                AND license_expiry != 'N/A'
                AND license_expiry LIKE '2025%'
            """)
            licenses_expiring_2025 = cursor.fetchone()["expiring_licenses"]
            
            return {
                "amount_overdue": round(amount_overdue, 2),
                "low_satisfaction_customers": int(low_satisfaction_customers),
                "licenses_expiring_2025": int(licenses_expiring_2025)
            }
            
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.get("/api/dashboard/company-contracts")
def get_company_contracts():
    try:
        with sqlite3.connect("databases/msp_data.db", timeout=30.0) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT company_id, company_name, contract_status, total_tickets, annual_revenue
                FROM company_contract
            """)
            rows = cursor.fetchall()

            contracts = [
                {
                    "company_id": r[0],
                    "company_name": r[1],
                    "contract_status": r[2],
                    "total_tickets": r[3],
                    "annual_revenue": r[4]
                }
                for r in rows
            ]

            return contracts
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/tickets/send")
def send_ticket():
    """
    Send the next ticket for processing
    """
    try:
        result = main.process_single_ticket()
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/tickets/timeline")
def get_ticket_timeline():
    """
    Get the current processing timeline
    """
    try:
        timeline = main.get_processing_timeline()
        return JSONResponse(content={"timeline": timeline}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/tickets/pending-approval")
def get_pending_approval():
    """
    Get tickets pending human approval
    """
    try:
        pending_tickets = main.get_pending_approval_tickets()
        return JSONResponse(content={"pending_tickets": pending_tickets}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

class TicketApprovalRequest(BaseModel):
    ticket_id: int
    approved: bool

@app.post("/api/tickets/approve")
def approve_ticket_endpoint(request: TicketApprovalRequest):
    """
    Approve or reject a ticket
    """
    try:
        result = main.approve_ticket(request.ticket_id, request.approved)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/tickets/initialize")
def initialize_ticket_system():
    """
    Initialize the ticket processing system
    """
    try:
        result = main.initialize_system()
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    

@app.get("/api/revenue-prediction")
def revenue_prediction():
    """
    API endpoint to get last 8 months of total_revenue and total_tickets,
    including prediction for current month.
    """
    try:
        data = predict_current_month()
        return {"data": data}
    except Exception as e:
        return {"error": str(e)}, 500
    

EXPORTS_DIR = Path("exports")

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """
    Download a file from the exports directory.
    
    Args:
        filename: Name of the file to download
    
    Returns:
        FileResponse with the requested file
    """
    if not filename.replace("_", "").replace("-", "").replace(".", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = EXPORTS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        file_path.resolve().relative_to(EXPORTS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if filename.endswith('.pdf'):
        media_type = 'application/pdf'
    elif filename.endswith('.xlsx'):
        media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        media_type = 'application/octet-stream'
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@app.get("/api/files/list")
async def list_files():
    """
    List all available files in the exports directory.
    Optional: Use this for file management.
    
    Returns:
        List of files with metadata
    """
    if not EXPORTS_DIR.exists():
        return {"files": []}
    
    files = []
    for file_path in EXPORTS_DIR.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            files.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "created": stat.st_ctime,
                "type": "pdf" if file_path.suffix == ".pdf" else "excel" if file_path.suffix == ".xlsx" else "other"
            })
    
    return {"files": sorted(files, key=lambda x: x["created"], reverse=True)}


@app.delete("/api/files/{filename}")
async def delete_file(filename: str):
    """
    Delete a file from the exports directory.
    Optional: For cleanup functionality.
    
    Args:
        filename: Name of the file to delete
    
    Returns:
        Success message
    """
    if not filename.replace("_", "").replace("-", "").replace(".", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = EXPORTS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        file_path.resolve().relative_to(EXPORTS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        os.remove(file_path)
        return {"message": f"File {filename} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
