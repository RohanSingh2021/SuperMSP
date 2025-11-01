import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain_tavily import TavilySearch
from typing import TypedDict
import json


requirement_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)
analyzer_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)
recommendation_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)

tavily = TavilySearch(max_results=5, tavily_api_key=os.getenv("TAVILY_API_KEY"))


requirement_prompt = ChatPromptTemplate.from_template("""
You are a software requirement extraction assistant.
Given a user's text describing their software needs, extract key fields as JSON:

Fields:
- required_features: list of main software categories (CRM, analytics, invoicing, etc.)
- team_size: number or range if mentioned
- budget: monthly or yearly if mentioned
- integrations: tools or systems to integrate with
- constraints: any other relevant details

Return only valid JSON.
User query:
{query}
""")

analyzer_prompt = ChatPromptTemplate.from_template("""
You are an expert software analyst.
Given a set of software search results, summarize each tool's:
- Core functionality
- Pricing
- Notable strengths
- Overlapping categories

Return a concise structured JSON list.

Results:
{results}
""")

recommendation_prompt = ChatPromptTemplate.from_template("""
You are a cost-optimization and software recommendation agent.

Given the user's requirements and analyzed tools, recommend the minimal set of tools
that cover all requirements while avoiding overlap.

Output should be concise and in JSON format:

{{
  "recommendations": [
    {{"name": "", "reason": "", "price": "", "category": "", "link": ""}}
  ],
  "total_estimated_cost": ""
}}

User Requirements:
{requirements}

Analyzed Tools:
{tools}
""")


def extract_requirements(state):
    """Extract requirements from user query using LLM"""
    user_query = state["user_query"]
    
    response = requirement_llm.invoke(requirement_prompt.format(query=user_query))
    
    try:
        
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1]
        if "```" in content:
            content = content.split("```")[0]
        
       
        content = content.strip()
        
        parsed = json.loads(content)
        return {"requirements": parsed}
    except Exception as e:
        return {"requirements": {"error": f"Failed to parse JSON: {str(e)}", "raw": response.content}}


def web_search_agent(state):
    """Search for software tools based on extracted requirements"""
    requirements = state["requirements"]
    if "error" in requirements:
        return {"search_results": []}

    features = ", ".join(requirements.get("required_features", []))
    budget = requirements.get("budget", "")
    integrations = ", ".join(requirements.get("integrations", []))

    query = f"Best {features} software tools under {budget} with integrations: {integrations}"
    try:
        search_results = tavily.invoke(query)
       
        return {
            "requirements": requirements,
            "search_results": search_results
        }
    except Exception as e:
        return {
            "requirements": requirements,
            "search_results": [{"title": "Error", "content": f"Search failed: {str(e)}"}]
        }


def analyze_features(state):
    """Analyze features of found software tools"""
    results = state["search_results"]
    
    if not results:
      
        return {
            "requirements": state.get("requirements", {}),
            "analyzed_tools": []
        }

    response = analyzer_llm.invoke(analyzer_prompt.format(results=json.dumps(results)))
    try:
       
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1]
        if "```" in content:
            content = content.split("```")[0]
        
  
        content = content.strip()
        

        return {
            "requirements": state.get("requirements", {}),
            "analyzed_tools": json.loads(content)
        }
    except Exception as e:

        return {
            "requirements": state.get("requirements", {}),
            "analyzed_tools": {"error": f"Failed to parse JSON: {str(e)}", "raw": response.content}
        }


def generate_recommendations(state):
    """Generate final recommendations based on requirements and analyzed tools"""
    requirements = state.get("requirements", {})
    tools = state.get("analyzed_tools", [])
    
    response = recommendation_llm.invoke(recommendation_prompt.format(
        requirements=json.dumps(requirements),
        tools=json.dumps(tools)
    ))

    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1]
        if "```" in content:
            content = content.split("```")[0]
        
        content = content.strip()
        
        return {"recommendations": json.loads(content)}
    except Exception as e:
        return {"recommendations": {"error": f"Failed to parse JSON: {str(e)}", "raw": response.content}}


graph = StateGraph(dict)

graph.add_node("extract_requirements", extract_requirements)
graph.add_node("web_search", web_search_agent)
graph.add_node("analyze_features", analyze_features)
graph.add_node("generate_recommendations", generate_recommendations)

graph.add_edge("extract_requirements", "web_search")
graph.add_edge("web_search", "analyze_features")
graph.add_edge("analyze_features", "generate_recommendations")

graph.set_entry_point("extract_requirements")
graph.set_finish_point("generate_recommendations")

compiled_app = graph.compile()


def get_software_recommendations(user_query: str, verbose: bool = False) -> dict:
    """
    Get software recommendations based on user requirements.
    
    Args:
        user_query: The user's software requirement description
        verbose: Whether to print debug information (default: False for API usage)
    
    Returns:
        dict: Contains recommendations and analysis results
    """
    if verbose:
        print(f"Processing query: {user_query}")
    
    result = compiled_app.invoke({"user_query": user_query})
    
    if verbose:
        print("\nFinal Recommendations:")
        print(json.dumps(result.get("recommendations", {}), indent=2))
    
    return result
