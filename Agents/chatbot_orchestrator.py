import os
import json
import time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import tool
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=GEMINI_API_KEY)

def is_rate_limit_error(error_message: str) -> bool:
    """
    Check if the error message indicates a rate limit error (429).
    """
    error_lower = str(error_message).lower()
    return "429" in error_lower or "rate limit" in error_lower or "quota exceeded" in error_lower

def handle_llm_call_with_rate_limit(llm_instance, messages):
    """
    Make an LLM call with rate limit error handling.
    
    Args:
        llm_instance: The LLM instance to use
        messages: Messages to send to the LLM
    
    Returns:
        dict: Either the LLM response or a rate limit error response
    """
    try:
        response = llm_instance.invoke(messages)
        return {"success": True, "response": response}
    except Exception as e:
        error_message = str(e)
        
        if is_rate_limit_error(error_message):
            return {
                "success": False,
                "is_rate_limit": True,
                "error": "⏱️ **Please wait for 2 minutes** - The per-minute API limit has been reached.\n\n" +
                        f"**Technical Details:** {error_message}"
            }
        else:
            return {
                "success": False,
                "is_rate_limit": False,
                "error": f"Error: {error_message}"
            }

from src.agents.financial_agent import handle_financial_query
from src.agents.license_audit_agent import handle_license_audit_query
from src.agents.company_specific_ticket_agent import handle_company_ticket_query
from src.agents.msp_insights_agent import handle_msp_insights_query
from email_agent import handle_email_command, get_help_text, send_emails
from file_generator import generate_file


AGENT_REGISTRY = {
    "financial_agent": {
        "func": handle_financial_query,
        "description": (
            "Specialized agent for client billing analytics, payment tracking, and price revision planning. "
            "Analyzes four key datasets: (1) overdue_payments - clients with no payments past-due invoices including "
            "company details, invoice amounts, due dates, and days overdue (status: 'Overdue' only); "
            "(2) delayed_payments - Clients who have made the payments but after the due date including"
            "company details, invoice amounts, due dates, and days overdue"
            "(3) upcoming_due_dates - pending invoices approaching payment deadlines with days until due "
            "(status: 'Pending' only); (4) price_revisions - annual pricing recommendations based on client "
            "behavior metrics (endpoints, happiness scores, ticket volume, contract length, payment delays) "
            "with detailed factor breakdowns (inflation, ticket impact, endpoint scale, payment penalties, "
            "happiness adjustments, contract discounts) and projected cost changes. Note: This agent does NOT "
            "have access to complete payment history or past transaction records - use msp_insights_agent for "
            "complete payment data by all the customers. Price revisions are forward-looking suggestions for next year's pricing "
            "based on current client behavior patterns."
        ),
        "expertise": [
            "Identifying clients with overdue payments and calculating total outstanding amounts",
            "Finding invoices due within specific timeframes (e.g., next 7, 14, 30 days)",
            "Analyzing payment delay patterns and days overdue by client or across portfolio",
            "Calculating proposed price increases/decreases and annual revenue impact per client",
            "Breaking down price revision factors (inflation, ticket volume, endpoint scale, payment behavior)",
            "Identifying clients at risk of price increases due to high ticket volume or payment delays",
            "Finding clients eligible for discounts based on long contracts or high happiness scores",
            "Comparing current vs. revised monthly costs and projecting annual financial changes",
            "Ranking clients by financial risk (overdue amounts, payment delays, revision severity)",
            "Generating payment reminders with contact details for overdue or upcoming invoices",
            "Estimating total revenue impact from implementing all proposed price revisions"
        ]
    },


    "license_audit_agent": {
        "func": handle_license_audit_query,
        "description": (
            "Specialized agent for software license compliance, cost optimization, and usage auditing. "
            "Analyzes two key datasets: (1) flagged_anomalous_access - customer_company_employees using software outside "
            "their typical role permissions, including employee details, software info, license costs, and "
            "violation reasons; (2) flagged_unused_software - licenses assigned but not actively used, "
            "including last usage timestamps, days since last use (or 'NEVER_USED'), license costs, and "
            "inactivity reasons. Provides actionable insights on license waste, unauthorized access, "
            "potential cost savings, and compliance violations across customer_company_employees, departments, and roles."
        ),
        "expertise": [
            "Identifying customer_company_employees with unused, idle, or never-used licenses",
            "Detecting unauthorized software access and role-based policy violations",
            "Calculating cost savings from removing or reclaiming unused licenses",
            "Finding licenses inactive for specific time periods (e.g., 30, 60, 90+ days)",
            "Analyzing anomalous access patterns by employee, role, or department",
            "Generating compliance violation reports and audit-ready summaries",
            "Tracking employee-level and department-level license utilization",
            "Identifying specific software with high waste or unauthorized usage",
            "Estimating total license costs for unused or non-compliant software",
            "Recommending license reclamation and reallocation opportunities"
        ]
    },

    "company_specific_ticket_agent": {
        "func": handle_company_ticket_query,
        "description": (
            "Specialized agent for customer company support ticket analytics and service quality assessment. "
            "Analyzes the company_analysis dataset containing aggregated metrics per MSP client company: "
            "resolved ticket counts, average resolution time in hours, employee satisfaction scores "
            "(average satisfaction of customer_company_employees within each customer company), and tickets_by_category "
            "(dictionary mapping ticket category names to ticket counts raised by that company's customer_company_employees). "
            "Provides comparative analysis across customer companies to identify service performance patterns, "
            "efficiency gaps, and satisfaction trends. This agent focuses on company-level aggregated metrics - "
            "for individual ticket details or employee-level ticket data, use other specialized agents."
        ),
        "expertise": [
            "Identifying companies with highest/lowest resolved ticket volumes",
            "Comparing average resolution times across customer companies",
            "Finding companies with declining or low employee satisfaction scores",
            "Analyzing ticket category distribution patterns by company (e.g., most common issue types)",
            "Identifying companies with longest resolution times requiring service improvement",
            "Ranking companies by service quality metrics (resolution speed, satisfaction)",
            "Detecting correlation between ticket volume and employee satisfaction scores",
            "Finding companies with disproportionately high tickets in specific categories",
            "Benchmarking company performance against portfolio averages or top performers",
            "Identifying service bottlenecks by comparing resolution times across companies",
            "Highlighting companies needing priority attention based on satisfaction or efficiency",
            "Analyzing which ticket categories are most prevalent across customer companies"
        ]
    },

    "msp_insights_agent": {
        "func": handle_msp_insights_query,
        "description": (
            "Comprehensive agent for MSP-wide business intelligence and cross-domain analytics. "
            "Analyzes six integrated datasets: (1) company_contract - contract status "
            "and annual revenue per client; (2) companies - complete client profiles including contact "
            "details, contract dates/length, endpoints; "
            "(3) payments - full payment history with invoice months, amounts due/paid, payment dates "
            "and delay days for ALL transactions; "
            "(4) technicians - MSP staff profiles with specializations, assigned ticket counts, and "
            "active status; (5) customer_company_employees - all customer company employees with company_id, department, "
            "role, location, join date, and assigned software; (6) software_inventory - complete software "
            "catalog with license costs, types, expiry dates, categories, and vendors. This is the primary "
            "agent for complete payment data, complete client portfolios, technician workload analysis, "
            "and cross-referencing relationships between companies, customer_company_employees, payments, and software. "
            "Use this agent for holistic MSP performance analysis and multi-domain queries."
        ),
        "expertise": [
            "Finding about the profitablity of the MSP"
            "Finding growth and service upselling opportunities for existing clients companies"
            "Finding categories of tickets which most raised by the customer companies and which categories are covered by sla agreement"
            "Identifying top revenue-generating clients and calculating total MSP revenue",
            "Analyzing complete payment history,",
            "Tracking contract status, renewal dates, and contract length distribution across portfolio",
            "Measuring technician workload distribution and identifying over/underutilized staff",
            "Analyzing employee distribution by company, department, role, or location",
            "Tracking software inventory costs, license expirations, and vendor relationships",
            "Finding clients with expiring contracts or licenses requiring renewal action",
            "Comparing client engagement metrics (endpoints, tickets, satisfaction) across portfolio",
            "Identifying technicians by specialization and matching to ticket requirements",
            "Calculating per-client profitability using revenue, ticket volume, and service costs",
            "Analyzing software assignment patterns across companies and employee roles",
            "Detecting inactive contracts, low-engagement clients, or at-risk accounts",
            "Cross-referencing payment patterns with contract terms and client satisfaction",
            "Generating portfolio-wide financial summaries and operational KPIs"
        ]
    }
}

def handle_slash_command(query: str) -> dict:
    """
    Handle slash commands for email, help, and pdf functionality.
    
    Returns dict with:
    - is_slash_command: bool
    - command_type: str (pdf, email, help, or None)
    - clean_query: str (query without slash command)
    - response: dict or None
    """
    query = query.strip()
    
    if not query.startswith('/'):
        return {
            "is_slash_command": False,
            "command_type": None,
            "clean_query": query,
            "response": None
        }
    
    parts = query[1:].split(maxsplit=1)
    if not parts:
        time.sleep(3)
        return {
            "is_slash_command": True,
            "command_type": None,
            "clean_query": "",
            "response": {"error": "Invalid command"}
        }
    
    command = parts[0].lower()
    remaining = parts[1] if len(parts) > 1 else ""
    
    if command == "pdf":
        if not remaining:
            time.sleep(3)
            return {
                "is_slash_command": True,
                "command_type": "pdf",
                "clean_query": "",
                "response": {"error": "Please provide a query after /pdf command"}
            }
        return {
            "is_slash_command": True,
            "command_type": "pdf",
            "clean_query": remaining,
            "response": None
        }
    
    
    if command == "help":
        help_text = get_help_text()
        
        time.sleep(2)
        return {
            "is_slash_command": True,
            "command_type": "help",
            "clean_query": "",
            "response": {
                "type": "help",
                "message": help_text
            }
        }
    
    if command.startswith("email-"):
        email_command = command[6:]  
        args = remaining.split() if remaining else []
        
        try:
            result = handle_email_command(email_command, args)
            result["type"] = "email"
            time.sleep(3)
            return {
                "is_slash_command": True,
                "command_type": "email",
                "clean_query": "",
                "response": result
            }
        except Exception as e:
            time.sleep(3)
            return {
                "is_slash_command": True,
                "command_type": "email",
                "clean_query": "",
                "response": {
                    "type": "email",
                    "status": "error",
                    "message": f"Error processing email command: {str(e)}"
                }
            }
    
    time.sleep(3)
    return {
        "is_slash_command": True,
        "command_type": None,
        "clean_query": "",
        "response": {
            "error": f"Unknown command: /{command}",
            "message": "Type /help to see available commands."
        }
    }


def handle_email_approval(approval_data: dict) -> dict:
    """
    Handle email sending after user approval.
    
    Args:
        approval_data: Dict containing 'approved' (bool) and 'emails' (list)
    
    Returns:
        Dict with send results
    """
    if not approval_data.get("approved"):
        return {
            "status": "cancelled",
            "message": "Email sending cancelled."
        }
    
    emails = approval_data.get("emails", [])
    
    if not emails:
        return {
            "status": "error",
            "message": "No emails to send."
        }
    
    return send_emails(emails)




def analyze_query_and_plan(user_query: str, verbose: bool = False) -> dict:
    """
    Analyzes the user query to determine complexity and create specific sub-queries for each agent.
    """
    agent_descriptions = "\n".join([
        f"- {name}: {info['description']}"
        for name, info in AGENT_REGISTRY.items()
    ])

    analysis_prompt = f"""
Analyze this financial query and create an execution plan for calling specialized agents.

Available agents:
{agent_descriptions}

User query: "{user_query}"

Your task:
1. Determine if this is "simple" (direct data lookup) or "complex" (needs strategic analysis)
2. Identify which agents have the data needed to answer this query
3. For EACH agent you select, write a SPECIFIC question that asks ONLY for the data you need from that agent

Important: Each agent is independent and only sees the question you give it. Formulate clear, focused questions.

Use the msp_insights agent for finding about the profitability of the MSP.

The data in the records is for the month of October and that is the only data that we have. Also info about 20 
customer employee is given. Consider this data to be complete. Dont make any changes in your query because of this information.

When the user asks about employees who have access to software which they shouldn't have, then they are referring to 
anamalous access of softwares and should be handles by license_audit_agent.

Examples:
- User: "Show overdue payments" 
  → simple, financial_agent: "List all companies with overdue payments including company name, amount overdue, and days overdue"

- User: "How can we improve profitability?"
  → complex, multiple agents:
     - financial_agent: "Show all proposed price revisions and calculate total potential revenue increase"
     - license_audit_agent: "Calculate total potential cost savings from unused licenses"
     - company_specific_ticket_agent: "Identify companies with poor satisfaction scores that may churn"

- User: "What is our total revenue?"
  → simple, msp_insights_agent: "Calculate the sum of annual revenue from all active client contracts"

Return JSON (no markdown, no explanations):
{{
    "complexity": "simple" or "complex",
    "requires_strategic_analysis": true or false,
    "agent_queries": {{
        "agent_name": "specific focused question for this agent",
        "another_agent_name": "different specific question for this agent"
    }}
}}
"""
    
    llm_result = handle_llm_call_with_rate_limit(llm, [{"role": "user", "content": analysis_prompt}])
    
    if not llm_result["success"]:
        return {
            "complexity": "simple",
            "requires_strategic_analysis": False,
            "agent_queries": {},
            "error": llm_result["error"],
            "is_rate_limit": llm_result.get("is_rate_limit", False)
        }
    
    response = llm_result["response"]
    
    if verbose:
        print(f"🤖 LLM Analysis Response:\n{response.content}\n")
    
    try:
        content = response.content.strip()
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        analysis = json.loads(content)
        
        if "agent_queries" not in analysis:
            raise ValueError("Missing 'agent_queries' in response")
        
        if not isinstance(analysis["agent_queries"], dict):
            raise ValueError("'agent_queries' must be a dictionary")
        
        return analysis
        
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Warning: JSON parsing failed: {e}")
        print(f"Warning: Raw content: {response.content[:500]}")
        
        identified_agents = {}
        for agent_name in AGENT_REGISTRY.keys():
            if agent_name in response.content.lower():
                identified_agents[agent_name] = user_query
        
        if not identified_agents:
            identified_agents = {list(AGENT_REGISTRY.keys())[0]: user_query}
        
        return {
            "complexity": "simple",
            "requires_strategic_analysis": False,
            "agent_queries": identified_agents
        }


def execute_agents_with_queries(agent_queries: dict, verbose: bool = False):
    """
    Executes agents in parallel with their specific queries.
    Returns only successful results, ignoring failures.
    """
    results = {}
    
    with ThreadPoolExecutor(max_workers=len(agent_queries)) as executor:
        future_to_agent = {}
        
        for agent, query in agent_queries.items():
            if agent in AGENT_REGISTRY:
                try:
                    future = executor.submit(AGENT_REGISTRY[agent]["func"], query)
                    future_to_agent[future] = {"agent": agent, "query": query}
                    if verbose:
                        print(f"Submitted {agent} with query: '{query[:50]}...'")
                except Exception as e:
                    if verbose:
                        print(f"Failed to submit {agent}: {e}")
        
        for future in as_completed(future_to_agent):
            agent_info = future_to_agent[future]
            agent_name = agent_info["agent"]
            try:
                result = future.result(timeout=30) 
                
                if verbose:
                    print(f"{agent_name} returned: {type(result)}")
                    print(f"   Data preview: {str(result)[:200]}...")
                
                if result is not None:
                    results[agent_name] = result
                    if verbose:
                        print(f"{agent_name} completed successfully")
                else:
                    if verbose:
                        print(f"Warning: {agent_name} returned None")
            except TimeoutError:
                if verbose:
                    print(f"⏱️ {agent_name} timed out after 30 seconds")
            except Exception as e:
                if verbose:
                    print(f"{agent_name} failed with error: {type(e).__name__}: {str(e)}")
    
    if verbose:
        print(f"\nSuccessfully retrieved data from {len(results)}/{len(agent_queries)} agents")
    
    return results


def synthesize_response(user_query: str, analysis: dict, agent_results: dict, verbose: bool = False):
    """
    Creates a concise response based on query complexity.
    """
    if not agent_results:
        return "I couldn't retrieve the requested information. Please try rephrasing your query."
    
    results_text = "\n\n".join([
        f"=== {agent_name.replace('_', ' ').title()} ===\n{json.dumps(result, indent=2)}"
        for agent_name, result in agent_results.items()
    ])
    
    is_complex = analysis.get("requires_strategic_analysis", False)
    
    if is_complex:
        synthesis_prompt = f"""
You are a financial analyst providing strategic insights for an MSP company.

User query: "{user_query}"

Available data:
{results_text}

Provide a strategic analysis with:
1. **Key Findings** (bullet points)
2. **Financial Impact** (quantify opportunities/risks with specific numbers)
3. **Recommendations** (prioritized, actionable steps)


If the user asks a question whose response is a list, then the final answer should contain entire list which was asked. Give the response
of a list on multiple lines with bullets rather than a large paragraph.

The data in the records is for the month of October and that is the only data that we have. Also info about 20 
customer employee is given. Consider this data to be complete. No need to mention this thing in the final response. 

Be crisp and data-driven. Use specific numbers from the data. Keep total response under 500 words.
"""
    else:
        synthesis_prompt = f"""
You are a financial assistant answering a specific query.

User query: "{user_query}"

Available data:
{results_text}

Provide a direct, concise answer:
- Answer the specific question asked
- Use exact numbers from the data
- Keep it under 250 words
- No unnecessary context or explanations

If the user asks a question whose response is a list, then the final answer should contain entire list which was asked. Give the response
of a list on multiple lines with bullets rather than a large paragraph.


If the data doesn't contain the answer, say so clearly.
"""
    
    llm_result = handle_llm_call_with_rate_limit(llm, [{"role": "user", "content": synthesis_prompt}])
    
    if not llm_result["success"]:
        return llm_result["error"]
    
    return llm_result["response"].content.strip()


def run_orchestrator(user_query: str, verbose: bool = True):
    """
    Main orchestrator that routes queries and provides concise responses.
    Handles slash commands, regular queries, and file exports (PDF/Excel).
    
    Args:
        user_query: The query to process
        verbose: Whether to print debug information
    
    Returns:
        dict: Contains response data (varies by query type)
    """

    slash_result = handle_slash_command(user_query)
    
    if slash_result["is_slash_command"]:
        command_type = slash_result["command_type"]
        
        if command_type in ["pdf", "excel"]:
            clean_query = slash_result["clean_query"]
            
            if not clean_query:
                return slash_result["response"]
            
            if verbose:
                print(f"File export requested: {command_type.upper()}")
                print(f"Processing query: {clean_query}\n")
            
            analysis_result = process_query(clean_query, verbose)
            
            try:
                if verbose:
                    print(f"\nGenerating {command_type.upper()} file...")
                
                filepath = generate_file(clean_query, analysis_result, command_type, include_agent_details=True)
                
                import os
                filename = os.path.basename(filepath)
                
                if verbose:
                    print(f"File generated successfully: {filepath}\n")
                
                return {
                    "type": "file_export",
                    "file_type": command_type,
                    "filename": filename,  
                    "filepath": filepath,  
                    "query": clean_query,
                    "complexity": analysis_result.get("complexity"),
                    "agents": analysis_result.get("agents", []),
                    "final_response": analysis_result.get("final_response"),
                    "message": f"{command_type.upper()} file generated successfully. Click the link below to download."
                }
                
            except Exception as e:
                error_msg = f"Error generating {command_type} file: {str(e)}"
                if verbose:
                    print(f"{error_msg}\n")
                
                return {
                    "type": "file_export",
                    "file_type": command_type,
                    "error": error_msg,
                    "message": f"Failed to generate {command_type} file."
                }
        else:
            return slash_result["response"]

    return process_query(user_query, verbose)


def process_query(user_query: str, verbose: bool = True):
    """
    Process a regular query (without slash commands).
    
    Args:
        user_query: The query to process
        verbose: Whether to print debug information
    
    Returns:
        dict: Contains analysis results
    """
    if verbose:
        print("Analyzing query...\n")
    
    analysis = analyze_query_and_plan(user_query, verbose)
    
    if "error" in analysis:
        return {
            "complexity": analysis.get("complexity", "simple"),
            "agents": [],
            "agent_results": {},
            "final_response": analysis["error"]
        }
    
    if verbose:
        print(f"Complexity: {analysis['complexity'].upper()}")
        print(f"Agent Queries: {json.dumps(analysis['agent_queries'], indent=2)}\n")
    
    agent_queries = analysis.get("agent_queries", {})
    
    if not agent_queries:
        return {
            "complexity": analysis["complexity"],
            "agents": [],
            "agent_results": {},
            "final_response": "I couldn't determine which data sources to query. Please rephrase your question."
        }
    
    if verbose:
        print(f"Executing {len(agent_queries)} agent(s)...\n")
    
    agent_results = execute_agents_with_queries(agent_queries, verbose)
    
    if not agent_results:
        return {
            "complexity": analysis["complexity"],
            "agents": list(agent_queries.keys()),
            "agent_results": {},
            "final_response": "No data was retrieved from the queried sources. The information may not be available."
        }
    
    if verbose:
        print("\nSynthesizing response...\n")
    
    final_response = synthesize_response(user_query, analysis, agent_results, verbose)
    
    if verbose:
        print("\n" + "="*70)
        print("ANALYSIS COMPLETE")
        print("="*70)
        print(final_response)
        print("="*70 + "\n")
    
    return {
        "complexity": analysis["complexity"],
        "requires_strategic_analysis": analysis.get("requires_strategic_analysis", False),
        "agents": list(agent_results.keys()),  
        "agent_results": agent_results,
        "final_response": final_response
    }
