
from collections import deque
import time
import threading
import requests
import base64
import os
from dotenv import load_dotenv
from agents.technician_agent import assign_ticket_llm

load_dotenv()


JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

auth_str = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
auth_encoded = base64.b64encode(auth_str.encode()).decode()

JIRA_HEADERS = {
    "Authorization": f"Basic {auth_encoded}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}


high_q = deque()
medium_q = deque()
low_q = deque()

queue_lock = threading.Lock()


PRIORITY_WEIGHTS = {"high": 5, "medium": 3, "low": 1}
priority_counters = PRIORITY_WEIGHTS.copy()



def push_ticket(ticket, timeline_entry=None):
    priority = ticket.get("priority", "low").lower()
    with queue_lock:
        if timeline_entry:
            ticket['_timeline_entry'] = timeline_entry
            
        if priority == "high":
            high_q.append(ticket)
            print(f"[Scheduler] Ticket pushed to HIGH queue: {ticket['title']}")
        elif priority == "medium":
            medium_q.append(ticket)
            print(f"[Scheduler] Ticket pushed to MEDIUM queue: {ticket['title']}")
        else:
            low_q.append(ticket)
            print(f"[Scheduler] Ticket pushed to LOW queue: {ticket['title']}")



def create_jira_ticket(ticket):
    """Creates a JIRA issue for the given ticket and returns the JIRA issue key."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": ticket["title"],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": ticket.get("description", "No description provided.")
                            }
                        ]
                    }
                ]
            },
            "issuetype": {"name": "Task"},
            "priority": {"name": ticket.get("priority", "Medium").capitalize()}
        }
    }

    response = requests.post(url, headers=JIRA_HEADERS, json=payload)
    if response.status_code == 201:
        issue_key = response.json()["key"]
        print(f"[JIRA] Created issue {issue_key} for ticket '{ticket['title']}'")
        ticket["jira_key"] = issue_key 
        return issue_key
    else:
        print(f"[JIRA] Failed to create issue: {response.status_code}, {response.text}")
        return None



def assign_jira_issue(issue_key, account_id):
    """
    Assigns an existing JIRA issue to a technician using their Atlassian account ID.
    """
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/assignee"
    payload = {"accountId": account_id}

    response = requests.put(url, headers=JIRA_HEADERS, json=payload)

    if response.status_code == 204:
        print(f"[JIRA] Assigned issue {issue_key} to account ID {account_id}")
        return True
    else:
        print(f"[JIRA] Failed to assign issue {issue_key}: {response.status_code}, {response.text}")
        return False

def scheduling_loop():
    global priority_counters
    while True:
        with queue_lock:
            for priority, queue in [("high", high_q), ("medium", medium_q), ("low", low_q)]:
                if queue and priority_counters[priority] > 0:
                    ticket = queue.popleft()
                    assigned = assign_ticket_llm(ticket)

                    if assigned:
                        print(f"[Scheduler] Ticket '{ticket['title']}' assigned to: {assigned['name']}")

                        issue_key = ticket.get("jira_key") or create_jira_ticket(ticket)

                        if issue_key and assigned.get("account_id"):
                            assign_jira_issue(issue_key, assigned["account_id"])
                        else:
                            print("[JIRA] Skipped JIRA assignment — missing issue key or technician account_id.")

                        if '_timeline_entry' in ticket:
                            timeline_entry = ticket['_timeline_entry']
                            timeline_entry["steps"].append(
                                f"Ticket {ticket.get('ticket_id', 'Unknown')} assigned to {assigned['name']} "
                                f"({assigned['specialization']})"
                            )
                            timeline_entry["status"] = "assigned"
                            timeline_entry["assigned_technician"] = {
                                "name": assigned['name'],
                                "specialization": assigned['specialization'],
                                "email": assigned['email']
                            }
                            if issue_key:
                                timeline_entry["jira_issue_key"] = issue_key
                    else:
                        print(f"[Scheduler] No technician free for ticket '{ticket['title']}', pushing back to queue")
                        queue.append(ticket)  

                    priority_counters[priority] -= 1
                    break  

            if all(c == 0 for c in priority_counters.values()):
                priority_counters = PRIORITY_WEIGHTS.copy()

        time.sleep(1)  
