import sqlite3
import time
import threading
import json
import asyncio
from pathlib import Path
from agents.rag_agent import get_rag_answer, initialize_rag
from agents import sla_agent, rag_agent, human_approval, scheduler
from websocket_manager import websocket_manager


DATABASE_PATH = Path(__file__).parent / "databases" / "msp_data.db"
TICKETS_JSON_PATH = Path(__file__).parent / "data" / "tickets.json"

current_ticket_index = 0
tickets_data = []
processing_timeline = []


def load_tickets():
    global tickets_data
    try:
        with open(TICKETS_JSON_PATH, 'r', encoding='utf-8') as f:
            tickets_data = json.load(f)
        
        tickets_data.sort(key=lambda x: x.get('ticket_id', 0))
        
        print(f"Loaded {len(tickets_data)} tickets from JSON file")
        return tickets_data
    except FileNotFoundError:
        raise Exception(f"Tickets JSON file not found at: {TICKETS_JSON_PATH}")
    except json.JSONDecodeError as e:
        raise Exception(f"Error parsing tickets JSON file: {e}")
    except Exception as e:
        raise Exception(f"Error loading tickets from JSON: {e}")


def get_technician_from_db(technician_id):
    """Get technician details from database"""
    if not technician_id:
        return None
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT technician_id, name, email, specialization
            FROM technicians
            WHERE technician_id = ?
        """, (technician_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return dict(result)
        return None
    except sqlite3.Error as e:
        print(f"Database error getting technician: {e}")
        return None


def update_ticket_assignment_in_db(ticket_id, technician_id, status=None):
    """Update ticket assignment and status in database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT ticket_id FROM tickets WHERE ticket_id = ?", (ticket_id,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO tickets (ticket_id, technician_id, status)
                VALUES (?, ?, ?)
            """, (ticket_id, technician_id, status or 'In Progress'))
        else:
            if status:
                cursor.execute("""
                    UPDATE tickets 
                    SET technician_id = ?, status = ?
                    WHERE ticket_id = ?
                """, (technician_id, status, ticket_id))
            else:
                cursor.execute("""
                    UPDATE tickets 
                    SET technician_id = ?
                    WHERE ticket_id = ?
                """, (technician_id, ticket_id))
        
        conn.commit()
        conn.close()
        print(f"Updated ticket {ticket_id} assignment in database")
        return True
    except sqlite3.Error as e:
        print(f"Database error updating ticket assignment: {e}")
        return False

def broadcast_timeline_update():
    """Broadcast timeline update via WebSocket"""
    try:
        timeline = get_processing_timeline()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    websocket_manager.broadcast_timeline_update(timeline), 
                    loop
                )
                print(f"Scheduled timeline update broadcast for {len(timeline)} entries")
            else:
                asyncio.run(websocket_manager.broadcast_timeline_update(timeline))
                print(f"Broadcasted timeline update for {len(timeline)} entries")
        except RuntimeError:
            asyncio.run(websocket_manager.broadcast_timeline_update(timeline))
            print(f"Broadcasted timeline update for {len(timeline)} entries")
    except Exception as e:
        print(f"Error broadcasting timeline update: {e}")

def broadcast_pending_tickets_update():
    """Broadcast pending tickets update via WebSocket"""
    try:
        pending_tickets = get_pending_approval_tickets()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    websocket_manager.broadcast_pending_tickets_update(pending_tickets), 
                    loop
                )
                print(f"Scheduled pending tickets update broadcast for {len(pending_tickets)} tickets")
            else:
                asyncio.run(websocket_manager.broadcast_pending_tickets_update(pending_tickets))
                print(f"Broadcasted pending tickets update for {len(pending_tickets)} tickets")
        except RuntimeError:
            asyncio.run(websocket_manager.broadcast_pending_tickets_update(pending_tickets))
            print(f"Broadcasted pending tickets update for {len(pending_tickets)} tickets")
    except Exception as e:
        print(f"Error broadcasting pending tickets update: {e}")


def process_single_ticket():
    global current_ticket_index, tickets_data, processing_timeline
    
    if current_ticket_index >= len(tickets_data):
        print("No more tickets to process")
        return {"status": "no_more_tickets", "message": "All tickets have been processed"}
    
    ticket = tickets_data[current_ticket_index]
    ticket_id = ticket.get('ticket_id', current_ticket_index + 1)
    
    print(f"\nProcessing ticket: {ticket['title']}")
    
    timeline_entry = {
        "ticket_id": ticket_id,
        "title": ticket['title'],
        "steps": []
    }
    
    timeline_entry["steps"].append(f"SLA check started for Ticket {ticket_id}")
    sla_result = sla_agent.check_sla(ticket)
    
    if not sla_result["covered"]:
        print(f"Ticket not covered by SLA: {sla_result['explanation']}")
        timeline_entry["steps"].append(f"SLA check failed for Ticket {ticket_id}: {sla_result['explanation']}")
        timeline_entry["status"] = "sla_failed"
        processing_timeline.append(timeline_entry)
        current_ticket_index += 1
        
        broadcast_timeline_update()
        broadcast_pending_tickets_update()
        
        return {
            "status": "sla_failed", 
            "message": f"Ticket {ticket_id} not covered by SLA",
            "timeline": processing_timeline
        }

    print(f"Ticket covered by SLA: {sla_result['explanation']}")
    timeline_entry["steps"].append(f"SLA check passed for Ticket {ticket_id}")

    timeline_entry["steps"].append(f"RAG processing started for Ticket {ticket_id}")
    ticket_text = ticket.get("title", "") + " " + ticket.get("description", "")
    rag_result = get_rag_answer(ticket_text, 5)
    ticket['rag_answer'] = rag_result['answer']
    print(f"RAG Answer: {rag_result['answer']}")
    timeline_entry["steps"].append(f"RAG processing completed for Ticket {ticket_id}")

    timeline_entry["steps"].append(f"Ticket {ticket_id} added to human approval queue")
    human_approval.add_to_human_queue(ticket)
    timeline_entry["status"] = "pending_approval"
    timeline_entry["rag_answer"] = rag_result['answer']
    
    processing_timeline.append(timeline_entry)
    current_ticket_index += 1
    
    broadcast_timeline_update()
    broadcast_pending_tickets_update()
    
    return {
        "status": "success", 
        "message": f"Ticket {ticket_id} processed and added to approval queue",
        "timeline": processing_timeline,
        "ticket": {
            "ticket_id": ticket_id,
            "title": ticket['title'],
            "rag_answer": rag_result['answer']
        }
    }


def get_processing_timeline():
    return list(reversed(processing_timeline))


def get_pending_approval_tickets():
    return list(human_approval.approval_queue)


def approve_ticket(ticket_id, approved):
    """Approve or reject a ticket by ticket_id"""
    for i, ticket in enumerate(human_approval.approval_queue):
        if ticket.get('ticket_id') == ticket_id:
            ticket['approved'] = approved
            approved_ticket = human_approval.approval_queue[i]
            del human_approval.approval_queue[i]
            
            for timeline_entry in processing_timeline:
                if timeline_entry["ticket_id"] == ticket_id:
                    if approved:
                        timeline_entry["steps"].append(f"Ticket {ticket_id} approved by human")
                        timeline_entry["status"] = "approved"
                        
                        update_ticket_assignment_in_db(ticket_id, None, "Approved")
                        
                        print(f"Ticket approved with rag answer: {approved_ticket['title']}")
                    else:
                        timeline_entry["steps"].append(f"Ticket {ticket_id} rejected, sent to scheduler")
                        timeline_entry["status"] = "sent_to_scheduler"
                        print(f"Ticket NOT approved, sending to scheduler: {approved_ticket['title']}")
                        
                        assigned_technician = scheduler.push_ticket(approved_ticket, timeline_entry)
                        
                        if assigned_technician:
                            update_ticket_assignment_in_db(ticket_id, assigned_technician.get('technician_id'), "Assigned")
                            timeline_entry["assigned_technician"] = assigned_technician
                            timeline_entry["steps"].append(f"Ticket {ticket_id} assigned to {assigned_technician.get('name', 'Unknown')}")
                    break
            
            broadcast_timeline_update()
            broadcast_pending_tickets_update()
            
            return {"status": "success", "message": f"Ticket {ticket_id} {'approved' if approved else 'rejected'}"}
    
    return {"status": "error", "message": f"Ticket {ticket_id} not found in approval queue"}


def start_human_approval_loop():
    print("Human approval system initialized (manual mode).")

def start_scheduler():
    t = threading.Thread(target=scheduler.scheduling_loop, daemon=True)
    t.start()
    print("Scheduler loop started in background.")


def initialize_system():
    """Initialize the ticket processing system"""
    global tickets_data
    tickets_data = load_tickets()
    start_human_approval_loop()
    start_scheduler()
    print(f"System initialized with {len(tickets_data)} tickets ready for processing")
    return {"status": "initialized", "total_tickets": len(tickets_data)}


if __name__ == "__main__":
    initialize_system()
    
    print("\nSystem ready. Tickets will be processed manually via API calls.")
    print("Use the Dashboard to send tickets for processing.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
