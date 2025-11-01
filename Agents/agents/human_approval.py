from collections import deque
import threading
import time
import requests
import time



approval_queue = deque()

def add_to_human_queue(ticket):
    approval_queue.append(ticket)
    print(f"Ticket added to human approval queue: {ticket['title']}")

def process_human_queue():
    while True:
        if approval_queue:
            ticket = approval_queue[0]
            print(f"\nTicket: {ticket['title']}")
            print(f"RAG Answer: {ticket['rag_answer']}")
            
            response = input("Approve? (y/n): ").strip().lower()
            ticket['approved'] = response == 'y'
            approval_queue.popleft()

            if ticket['approved']:
                print(f"Ticket approved with rag answer: {ticket['title']}")
            else:
                from agents import scheduler  
                print(f"Ticket NOT approved, sending to scheduler: {ticket['title']}")
                scheduler.push_ticket(ticket)
        else:
            time.sleep(2)  
