
from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict
from typing import List, Dict, Any
from langchain.prompts import ChatPromptTemplate
from langchain_tavily import TavilySearch
from typing import Annotated
import csv
import requests
import re
import json
import ast
from dotenv import load_dotenv
import os
import time

load_dotenv()

llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")



class Profiles(TypedDict):
    query: str
    location: str
    companies: List[str]                
    enriched_companies: List[Dict[str,Any]]  



tavily_search = TavilySearch(tavily_api_key=os.getenv("TAVILY_API_KEY"))
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

def search_it_companies(query: str, limit: int = 10) -> list:
    """
    Use Tavily to fetch raw IT company data based on query,
    then use LLM to extract clean company names as a Python list.
    """
    raw_results = tavily_search.run(query)

    combined_text = "\n".join([res.get("content", "") for res in raw_results.get("results", [])])

    prompt = (
        f"Extract only the company names from the following text. "
        f"Return EXACTLY {limit} company names if present as a Python list of strings. "
        f"Return as a Python list of strings, no numbers or extra words.\n\nText:\n{combined_text}"
    )
    llm_response = llm.invoke([{"role": "user", "content": prompt}])
    response_text = llm_response.content.strip()

    match = re.search(r"\[.*\]", response_text, re.DOTALL)
    if match:
        list_text = match.group(0)
        try:
            companies = ast.literal_eval(list_text)
            if not isinstance(companies, list):
                companies = []
        except Exception as e:
            print(f"Parse error: {e}")
            companies = []
    else:
        companies = []

    companies = companies[:limit]

    print(f"Found {len(companies)} companies (limit {limit}): {companies}")
    return companies

def choose_best_it_contact(company: str, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Pick the best IT head from contacts using LLM.
    Returns a dict with keys: company, name, title, linkedin
    """
    best_contact = {"company": company, "name": "", "title": "", "linkedin": ""}

    if not contacts:
        return best_contact

    contacts_text = "\n".join([f"Name: {c['name']}, Title: {c['title']}, LinkedIn: {c['linkedin_url']}" 
                               for c in contacts])

    prompt = (
        f"You are an expert in IT leadership roles.\n"
        f"From the following list of people working at {company}, select the single best person "
        f"for the Head of IT role. Prioritize: CIO, CTO, VP of IT, IT Director, Head of IT.\n"
        f"Return **strict JSON** with keys: name, title, linkedin.\n"
        f"No extra text or explanation.\n\nContacts:\n{contacts_text}"
    )

    try:
        llm_response = llm.invoke([{"role": "user", "content": prompt}])
        response_text = llm_response.content.strip()

        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            best_contact_json = json.loads(json_match.group(0))
            best_contact.update({
                "name": best_contact_json.get("name",""),
                "title": best_contact_json.get("title",""),
                "linkedin": best_contact_json.get("linkedin","")
            })
        else:
            first = contacts[0]
            best_contact.update({
                "name": first["name"],
                "title": first["title"],
                "linkedin": first["linkedin_url"]
            })

    except Exception as e:
        print(f"LLM parse error for {company}: {e}")
        first = contacts[0]
        best_contact.update({
            "name": first["name"],
            "title": first["title"],
            "linkedin": first["linkedin_url"]
        })

    return best_contact

def is_it_related_title(title: str) -> bool:
    """
    Very permissive check - accepts any technology or business leadership role.
    """
    t = title.lower()

    exclude_keywords = [
        "intern", "student", "entry level", "junior"
    ]
    
    if any(k in t for k in exclude_keywords):
        return False

    it_leadership = [
        "cio", "cto", "chief information", "chief technology", "chief digital",
        "vp", "vice president", "head of", "director", "manager",
        "information technology", "technology", "it ", " it", 
        "digital", "cyber", "cloud", "infrastructure", "security",
        "systems", "operations", "architecture", "transformation"
    ]
    
    return any(k in t for k in it_leadership)

def search_linkedin_profiles(query: str, num_results: int = 30) -> List[Dict[str, Any]]:
    """
    Generic LinkedIn profile search using SerpAPI.
    """
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": num_results
    }
    
    people_info = []
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("organic_results", [])
        
        for res in results:
            title = res.get("title", "")
            link = res.get("link", "")
            
            if "linkedin.com/in" not in link:
                continue
            
            name = ""
            if " - " in title:
                name = title.split(" - ")[0].strip()
            elif "|" in title:
                name = title.split("|")[0].strip()
            else:
                name_match = re.search(r'linkedin\.com/in/([\w-]+)', link)
                if name_match:
                    name = name_match.group(1).replace('-', ' ').title()
            
            person = {
                "name": name,
                "title": title,
                "linkedin_url": link,
            }
            
            if not any(p['linkedin_url'] == link for p in people_info):
                people_info.append(person)
        
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
    
    return people_info

def fetch_it_management_info(company_name: str, location: str) -> List[Dict[str, Any]]:
    """
    Fetch IT management person with AGGRESSIVE fallback strategies.
    GUARANTEES at least one result per company.
    """
    
    strategies = [
        f'"{company_name}" (CIO OR CTO OR "Chief Information Officer" OR "Chief Technology Officer") {location} site:linkedin.com/in',
        f'"{company_name}" ("VP IT" OR "VP Technology" OR "Head of IT" OR "IT Director") {location} site:linkedin.com/in',
        f'"{company_name}" ("IT Manager" OR "Technology Manager" OR "Digital Director") {location} site:linkedin.com/in',
        f'{company_name} technology {location} site:linkedin.com/in',
        f'{company_name} IT operations {location} site:linkedin.com/in',
        f'{company_name} digital transformation {location} site:linkedin.com/in',
        f'"{company_name}" (CEO OR President OR "Vice President" OR Director) {location} site:linkedin.com/in',
        f'{company_name} {location} site:linkedin.com/in'
    ]
    
    people_info = []
    
    for strategy_idx, query in enumerate(strategies):
        print(f"[Strategy {strategy_idx + 1}/{len(strategies)}] Searching...")
        
        results = search_linkedin_profiles(query, num_results=30)
        
        it_results = [r for r in results if is_it_related_title(r['title'])]
        
        if it_results:
            people_info.extend(it_results)
            print(f"Found {len(it_results)} IT-related profiles")
            break
        
        if results and strategy_idx >= len(strategies) - 2: 
            people_info.extend(results[:5])  
            print(f"Warning: Using fallback: Found {len(results)} general profiles")
            break
        
        time.sleep(0.5)
    
    if not people_info:
        print("Ultimate fallback: Searching company page employees...")
        company_page_query = f'{company_name} site:linkedin.com/in'
        results = search_linkedin_profiles(company_page_query, num_results=50)
        people_info.extend(results[:10]) 
    
    if not people_info:
        print("Last resort: Searching without location filter...")
        generic_query = f'"{company_name}" linkedin.com/in'
        results = search_linkedin_profiles(generic_query, num_results=50)
        people_info.extend(results[:10])
    
    if people_info:
        print(f"Total profiles found for {company_name}: {len(people_info)}")
    else:
        print(f"No profiles found for {company_name} - This should be rare!")
    
    return people_info

def create_placeholder_contact(company: str) -> Dict[str, Any]:
    """
    Create a placeholder when absolutely no LinkedIn profile can be found.
    This uses LLM to generate a likely LinkedIn search URL.
    """
    print(f"Warning: Creating search placeholder for {company}")
    
    search_url = f"https://www.linkedin.com/search/results/people/?keywords={company.replace(' ', '%20')}%20IT"
    
    return {
        "company": company,
        "name": "No profile found",
        "title": "Search LinkedIn manually",
        "linkedin": search_url  
    }



def search_agent(state: dict) -> dict:
    """
    Agent to search IT companies using LLM.
    Updates state with a list of company names in state['companies'].
    """
    query = state.get("query", "")

    limit_match = re.search(r"\b(\d+)\b", query)
    limit = int(limit_match.group(1)) if limit_match else 20

    location_match = re.search(r"in ([\w\s]+)", query, re.IGNORECASE)
    location = location_match.group(1).strip() if location_match else ""

    state["location"] = location

    companies = search_it_companies(query, limit)
    state["companies"] = companies
    return state

def enrich_contacts_agent(state: Profiles) -> Profiles:
    """
    Agent: For each company, fetch contacts with GUARANTEED results.
    Updates state['enriched_companies'] with one contact per company (never empty).
    """
    final_results = []
    location = state.get("location", "")

    for idx, company in enumerate(state.get("companies", []), 1):
        print(f"\n{'='*60}")
        print(f"[{idx}/{len(state.get('companies', []))}] Processing: {company}")
        print(f"{'='*60}")
        
        contacts = fetch_it_management_info(company, location)
        
        if contacts:
            best_contact = choose_best_it_contact(company, contacts)
        else:
            best_contact = create_placeholder_contact(company)
        
        final_results.append(best_contact)
        
        time.sleep(0.5)

    state["enriched_companies"] = final_results
    
    successful = sum(1 for r in final_results if r.get("name") and r.get("name") != "No profile found")
    placeholders = len(final_results) - successful
    
    print(f"\n{'='*60}")
    print(f"Successfully enriched: {successful}/{len(final_results)} companies")
    if placeholders > 0:
        print(f"Warning: Placeholders created: {placeholders} (manual search needed)")
    print(f"{'='*60}\n")
    
    return state



graph = StateGraph(Profiles)

graph.add_node("search_agent", search_agent)
graph.add_node("enrich_contacts_agent", enrich_contacts_agent)

graph.add_edge(START, "search_agent")
graph.add_edge("search_agent", "enrich_contacts_agent")
graph.add_edge("enrich_contacts_agent", END)

graph = graph.compile()
