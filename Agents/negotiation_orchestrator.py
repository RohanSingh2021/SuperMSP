
import os
import json
from pathlib import Path
from typing import List, Dict, Any, TypedDict, Annotated
from datetime import datetime
import operator

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

from unstructured.partition.auto import partition
import pdfplumber
import PyPDF2

load_dotenv()

UPLOADS_FOLDER = "uploads"
RESULTS_FOLDER = "negotiation_results"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def manage_results_folder():
    """Manage negotiation_results folder: create if not exists, clear if has content"""
    print(f"Managing results folder: {RESULTS_FOLDER}")
    
    if not os.path.exists(RESULTS_FOLDER):
        print(f"  Creating new folder: {RESULTS_FOLDER}")
        os.makedirs(RESULTS_FOLDER)
    else:
        print(f"  Folder exists: {RESULTS_FOLDER}")
        
        existing_files = list(Path(RESULTS_FOLDER).iterdir())
        if existing_files:
            print(f"  Found {len(existing_files)} existing files, clearing folder...")
            for file_path in existing_files:
                if file_path.is_file():
                    os.remove(file_path)
                    print(f"    Deleted: {file_path.name}")
                elif file_path.is_dir():
                    import shutil
                    shutil.rmtree(file_path)
                    print(f"    Deleted directory: {file_path.name}")
            print(f"  Folder cleared successfully")
        else:
            print(f"  Folder is empty, ready for new files")

if __name__ == "__main__":
    manage_results_folder()


class AgentState(TypedDict):
    """State for the negotiation agent"""
    documents: List[Dict[str, Any]]
    extracted_data: List[Dict[str, Any]]
    key_points: List[Dict[str, Any]]
    unified_comparison: Dict[str, Any]
    recommendation: Dict[str, Any]
    messages: Annotated[List, operator.add]
    current_step: str


class DocumentExtractor:
    """Extract content from various document formats"""
    
    @staticmethod
    def extract_pdf(file_path: str) -> Dict[str, Any]:
        """Extract text and tables from PDF using multiple methods"""
        content = {"text": "", "tables": [], "metadata": {}, "raw_extractions": []}
        
        try:
            text_parts = []
            tables = []
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"\n--- Page {page_num} ---\n{page_text}")
                    
                    page_tables = page.extract_tables()
                    for table_idx, table in enumerate(page_tables):
                        if table:
                            tables.append({
                                "page": page_num,
                                "table_index": table_idx,
                                "data": table
                            })
            
            content["text"] = "\n".join(text_parts)
            content["tables"] = tables
            content["raw_extractions"].append({"method": "pdfplumber", "success": True})
            print(f"    pdfplumber: Extracted {len(text_parts)} pages, {len(tables)} tables")
            
        except Exception as e:
            print(f"    Warning: pdfplumber failed: {e}")
            content["raw_extractions"].append({"method": "pdfplumber", "success": False, "error": str(e)})
        
        if not content["text"]:
            try:
                text_parts = []
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page_num, page in enumerate(pdf_reader.pages, 1):
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(f"\n--- Page {page_num} ---\n{page_text}")
                
                if text_parts:
                    content["text"] = "\n".join(text_parts)
                    print(f"    PyPDF2: Extracted {len(text_parts)} pages")
                    content["raw_extractions"].append({"method": "PyPDF2", "success": True})
                
            except Exception as e:
                print(f"    Warning: PyPDF2 failed: {e}")
                content["raw_extractions"].append({"method": "PyPDF2", "success": False, "error": str(e)})
        
        if not content["text"]:
            try:
                elements = partition(filename=file_path)
                text_content = []
                tables = []
                
                for element in elements:
                    element_type = str(type(element).__name__)
                    if "Table" in element_type:
                        tables.append(str(element))
                    else:
                        text_content.append(str(element))
                
                if text_content:
                    content["text"] = "\n".join(text_content)
                if tables and not content["tables"]:
                    content["tables"] = tables
                
                print(f"    unstructured: Extracted text and {len(tables)} tables")
                content["raw_extractions"].append({"method": "unstructured", "success": True})
                
            except Exception as e:
                print(f"    Warning: unstructured failed: {e}")
                content["raw_extractions"].append({"method": "unstructured", "success": False, "error": str(e)})
        
        content["metadata"] = {"file_name": os.path.basename(file_path)}
        
        if not content["text"] and not content["tables"]:
            print(f"    All extraction methods failed for PDF")
            content["error"] = "All extraction methods failed"
        
        return content
    
    
    
    
    @classmethod
    def extract_document(cls, file_path: str) -> Dict[str, Any]:
        """Extract content based on file type - PDF only"""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return cls.extract_pdf(file_path)
        else:
            return {
                "text": "",
                "tables": [],
                "metadata": {"file_name": os.path.basename(file_path)},
                "error": f"Unsupported file type: {ext}. Only PDF files are supported."
            }


def remove_null_values(data):
    """Recursively remove keys with null, empty string, or empty list/dict values"""
    if isinstance(data, dict):
        return {
            k: remove_null_values(v)
            for k, v in data.items()
            if v is not None and v != "" and v != [] and v != {}
        }
    elif isinstance(data, list):
        return [remove_null_values(item) for item in data if item is not None and item != "" and item != {} and item != []]
    else:
        return data


class NegotiationsAgent:
    """Main agent for analyzing license quotations"""
    
    def __init__(self, api_key: str):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1
        )
        self.extractor = DocumentExtractor()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        workflow.add_node("load_documents", self.load_documents)
        workflow.add_node("extract_data", self.extract_data)
        workflow.add_node("extract_key_points", self.extract_key_points)
        workflow.add_node("unified_comparison", self.unified_comparison)
        workflow.add_node("generate_recommendation", self.generate_recommendation)
        workflow.add_node("save_results", self.save_results)
        
        workflow.set_entry_point("load_documents")
        workflow.add_edge("load_documents", "extract_data")
        workflow.add_edge("extract_data", "extract_key_points")
        workflow.add_edge("extract_key_points", "unified_comparison")
        workflow.add_edge("unified_comparison", "generate_recommendation")
        workflow.add_edge("generate_recommendation", "save_results")
        workflow.add_edge("save_results", END)
        
        return workflow.compile()
    
    def load_documents(self, state: AgentState) -> AgentState:
        """Load all documents from uploads folder"""
        print("Loading documents from uploads folder...")
        
        documents = []
        uploads_path = Path(UPLOADS_FOLDER)
        
        if not uploads_path.exists():
            print(f"Warning: Uploads folder not found: {UPLOADS_FOLDER}")
            state["documents"] = []
            state["current_step"] = "load_documents"
            return state
        
        for file_path in uploads_path.iterdir():
            if file_path.is_file():
                documents.append({
                    "path": str(file_path),
                    "name": file_path.name,
                    "extension": file_path.suffix
                })
                print(f"  Found: {file_path.name}")
        
        state["documents"] = documents
        state["current_step"] = "load_documents"
        state["messages"] = [SystemMessage(content=f"Loaded {len(documents)} documents")]
        
        return state
    
    def extract_data(self, state: AgentState) -> AgentState:
        """Extract data from all documents"""
        print("\nExtracting data from documents...")
        
        extracted_data = []
        
        for doc in state["documents"]:
            print(f"  Processing: {doc['name']}")
            content = self.extractor.extract_document(doc["path"])
            
            extracted_data.append({
                "file_name": doc["name"],
                "content": content
            })
        
        state["extracted_data"] = extracted_data
        state["current_step"] = "extract_data"
        
        return state
    
    def extract_key_points(self, state: AgentState) -> AgentState:
        """Extract structured key points from each quotation - only non-null values"""
        print("\nExtracting key points from each quotation...")
        
        key_points_list = []
        
        for idx, data in enumerate(state["extracted_data"], 1):
            print(f"  Extracting key points from: {data['file_name']}")
            
            content_text = data["content"]["text"]
            tables_text = "\n\n".join([str(table) for table in data["content"]["tables"]])
            full_content = f"{content_text}\n\nTables:\n{tables_text}"
            
            extraction_prompt = f"""
You are an expert procurement analyst. Extract ALL key points and important details from this license quotation.

DOCUMENT: {data['file_name']}

CONTENT:
{full_content[:80000]}

Extract and structure the following information in JSON format. 

CRITICAL RULES:
1. ONLY include fields where you found actual information in the document
2. DO NOT include fields with null, empty strings, or empty arrays
3. If information is not present in the document, simply omit that field entirely
4. Extract EXACT values, numbers, dates, and terms from the document
5. Do not make assumptions - only extract what is explicitly stated
6. Return ONLY valid JSON with no null values

STRUCTURE (only include fields with actual data):

{{
  "vendor_information": {{
    "vendor_name": "",
    "contact_details": "",
    "quotation_number": "",
    "quotation_date": "",
    "validity_period": "",
    "sales_representative": ""
  }},
  "pricing": {{
    "base_price": "",
    "currency": "",
    "price_per_license": "",
    "total_licenses": "",
    "volume_discounts": [],
    "setup_fees": "",
    "implementation_cost": "",
    "training_cost": "",
    "maintenance_annual": "",
    "support_annual": "",
    "hidden_costs": [],
    "payment_terms": "",
    "payment_schedule": "",
    "early_payment_discount": "",
    "late_payment_penalty": ""
  }},
  "license_details": {{
    "license_type": "",
    "license_model": "",
    "number_of_users": "",
    "concurrent_users": "",
    "named_users": "",
    "license_scope": "",
    "geographic_restrictions": "",
    "usage_restrictions": "",
    "transfer_rights": "",
    "resale_rights": "",
    "backup_licenses": ""
  }},
  "contract_terms": {{
    "contract_duration": "",
    "start_date": "",
    "end_date": "",
    "renewal_type": "",
    "renewal_notice_period": "",
    "auto_renewal": "",
    "cancellation_policy": "",
    "cancellation_notice": "",
    "cancellation_penalty": "",
    "price_increase_terms": "",
    "price_protection": ""
  }},
  "support_and_maintenance": {{
    "support_level": "",
    "support_hours": "",
    "response_time_critical": "",
    "response_time_high": "",
    "response_time_medium": "",
    "response_time_low": "",
    "dedicated_support": "",
    "support_channels": [],
    "updates_included": "",
    "upgrade_policy": "",
    "upgrade_cost": "",
    "maintenance_windows": ""
  }},
  "service_level_agreement": {{
    "uptime_guarantee": "",
    "performance_metrics": [],
    "penalties_for_breach": "",
    "credits_for_downtime": "",
    "exclusions": []
  }},
  "implementation_and_training": {{
    "onboarding_included": "",
    "training_sessions": "",
    "training_materials": "",
    "implementation_timeline": "",
    "migration_support": "",
    "customization_included": "",
    "integration_support": ""
  }},
  "legal_and_compliance": {{
    "liability_cap": "",
    "indemnification": "",
    "warranty": "",
    "warranty_period": "",
    "data_ownership": "",
    "data_privacy": "",
    "compliance_certifications": [],
    "audit_rights": "",
    "jurisdiction": "",
    "dispute_resolution": ""
  }},
  "termination_and_exit": {{
    "termination_for_convenience": "",
    "termination_notice": "",
    "data_export": "",
    "data_deletion": "",
    "transition_assistance": "",
    "refund_policy": ""
  }},
  "red_flags": [],
  "unique_benefits": []
}}

Remember: Only include fields where actual information was found. Omit all others.
"""
            
            try:
                response = self.llm.invoke([HumanMessage(content=extraction_prompt)])
                
                try:
                    key_points_json = json.loads(response.content.strip().replace("```json", "").replace("```", "").strip())
              
                    key_points_json = remove_null_values(key_points_json)
                except:
                    key_points_json = {"raw_extraction": response.content}
                
                key_points_list.append({
                    "file_name": data['file_name'],
                    "key_points": key_points_json,
                    "extraction_timestamp": datetime.now().isoformat()
                })
                
                print(f"    Extracted key points successfully")
                
            except Exception as e:
                print(f"    Warning: Error extracting key points: {e}")
                key_points_list.append({
                    "file_name": data['file_name'],
                    "key_points": {"error": str(e)},
                    "extraction_timestamp": datetime.now().isoformat()
                })
        
        state["key_points"] = key_points_list
        state["current_step"] = "extract_key_points"
        
        return state
    
    def unified_comparison(self, state: AgentState) -> AgentState:
        """Compare all key points across all quotations in a unified manner"""
        print("\nPerforming unified comparison across all quotations...")
        
        try:
          
            if not state.get("key_points") or len(state["key_points"]) == 0:
                print("    Warning: No key points data available for comparison")
                unified_comparison = {
                    "comparison": "No key points data available for unified comparison. Please ensure documents were processed successfully in the previous step.",
                    "quotations_compared": 0,
                    "comparison_timestamp": datetime.now().isoformat(),
                    "error": "No key points data",
                    "status": "failed"
                }
                state["unified_comparison"] = unified_comparison
                state["current_step"] = "unified_comparison"
                return state
            
            
            all_key_points = {}
            valid_quotations = 0
            
            for kp_data in state["key_points"]:
                if not isinstance(kp_data, dict) or 'file_name' not in kp_data or 'key_points' not in kp_data:
                    print(f"    Warning: Skipping invalid key points data: {kp_data}")
                    continue
                
                file_name = kp_data['file_name']
                key_points = kp_data['key_points']
                
              
                if isinstance(key_points, dict) and 'error' in key_points:
                    print(f"    Warning: Key points extraction failed for {file_name}: {key_points['error']}")
                  
                    all_key_points[file_name] = {"extraction_failed": True, "error": key_points['error']}
                elif key_points:
                    all_key_points[file_name] = key_points
                    valid_quotations += 1
                else:
                    print(f"    Warning: Empty key points for {file_name}")
                    all_key_points[file_name] = {"extraction_failed": True, "error": "Empty key points"}
            
            print(f"    Comparing {len(all_key_points)} quotations ({valid_quotations} valid)")
            
            if valid_quotations == 0:
                unified_comparison = {
                    "comparison": "No valid key points data available for comparison. All document extractions failed.",
                    "quotations_compared": len(all_key_points),
                    "comparison_timestamp": datetime.now().isoformat(),
                    "error": "No valid extractions",
                    "status": "failed"
                }
                state["unified_comparison"] = unified_comparison
                state["current_step"] = "unified_comparison"
                return state
            
           
            try:
                key_points_json = json.dumps(all_key_points, indent=2, ensure_ascii=False, default=str)
                print(f"    Key points data size: {len(key_points_json):,} characters")
            except (TypeError, ValueError) as json_error:
                print(f"    JSON serialization failed: {json_error}")
              
                simplified_points = {}
                for file_name, points in all_key_points.items():
                    if isinstance(points, dict):
                        simplified_points[file_name] = {k: str(v) for k, v in points.items()}
                    else:
                        simplified_points[file_name] = str(points)
                key_points_json = json.dumps(simplified_points, indent=2, ensure_ascii=False)
                print(f"    Simplified key points data size: {len(key_points_json):,} characters")
            
           
            max_prompt_size = 100000
            if len(key_points_json) > max_prompt_size:
                print(f"    Warning: Key points data too large ({len(key_points_json):,} chars), truncating...")
                key_points_json = key_points_json[:max_prompt_size] + "\n... [Data truncated due to size limits]"
            
            unified_comparison_prompt = f"""
Compare these {len(all_key_points)} quotations and provide a concise analysis.

QUOTATION DATA:
{key_points_json}

Provide a brief comparison covering:

1. **PRICING SUMMARY**:
   - Compare base prices, setup fees, annual costs
   - Identify cheapest and most expensive options
   - Note any hidden costs

2. **KEY TERMS**:
   - Contract duration and renewal terms
   - License restrictions and user limits
   - Payment terms and cancellation policies

3. **SUPPORT & FEATURES**:
   - Support levels and response times
   - Training and implementation included
   - Key feature differences

4. **RECOMMENDATION**:
   - Best overall value
   - Main pros/cons for each vendor
   - Key negotiation points

Keep response under 2000 words. Focus on the most important differences for decision making.
"""
            
            print(f"    Prompt size: {len(unified_comparison_prompt):,} characters")
            print("    Invoking LLM for unified comparison...")
            
           
            try:
                response = self.llm.invoke([HumanMessage(content=unified_comparison_prompt)])
                
                if not response or not response.content:
                    raise ValueError("Empty response from LLM")
                
                unified_comparison = {
                    "comparison": response.content,
                    "quotations_compared": len(all_key_points),
                    "valid_quotations": valid_quotations,
                    "comparison_timestamp": datetime.now().isoformat(),
                    "response_length": len(response.content),
                    "data_size": len(key_points_json),
                    "status": "success"
                }
                
                print(f"    Unified comparison complete ({len(response.content):,} characters)")
                
            except Exception as llm_error:
                print(f"    LLM API call failed: {llm_error}")
                unified_comparison = {
                    "comparison": f"LLM API call failed: {str(llm_error)}\n\nThe system was unable to generate a unified comparison due to an API error. Please check your API key and try again.",
                    "quotations_compared": len(all_key_points),
                    "valid_quotations": valid_quotations,
                    "comparison_timestamp": datetime.now().isoformat(),
                    "error": str(llm_error),
                    "status": "failed"
                }
            
        except Exception as e:
            print(f"    Error in unified comparison: {e}")
            import traceback
            traceback.print_exc()
            
        
            unified_comparison = {
                "comparison": f"Error during unified comparison: {str(e)}\n\nThis error occurred while processing the dataset. The system attempted to analyze all available data but encountered an issue.",
                "quotations_compared": len(state.get("key_points", [])),
                "comparison_timestamp": datetime.now().isoformat(),
                "error": str(e),
                "status": "failed"
            }
        
        state["unified_comparison"] = unified_comparison
        state["current_step"] = "unified_comparison"
        
        return state
    
    def generate_recommendation(self, state: AgentState) -> AgentState:
        """Generate concise recommendation in the requested format"""
        print("\n� Generating concise recommendation...")
        
        vendor_info = {}
        for kp_data in state["key_points"]:
            file_name = kp_data['file_name']
            vendor_name = kp_data['key_points'].get('vendor_information', {}).get('vendor_name', file_name)
            vendor_info[file_name] = vendor_name
        
        recommendation_prompt = f"""
Based on the analysis, create a CONCISE report in the exact format requested.

UNIFIED COMPARISON:
{state['unified_comparison']['comparison'][:60000]}

KEY POINTS FOR ALL VENDORS:
{json.dumps([kp['key_points'] for kp in state['key_points']], indent=2)[:50000]}

Create a SHORT, TO-THE-POINT report in this EXACT JSON format:

{{
  "analysis_date": "{datetime.now().isoformat()}",
  "vendor_analysis": {{
    "vendor_a": {{
      "vendor_name": "Vendor A Name",
      "pros": [
        "List 3-5 key advantages",
        "Be specific and concise",
        "Focus on most important benefits"
      ],
      "cons": [
        "List 3-5 key disadvantages", 
        "Be specific about problems",
        "Focus on major concerns"
      ],
      "negotiation_strategy": "Single concise sentence about main negotiation approach (e.g., 'Ask for reducing price as Vendor B is providing lower cost')"
    }},
    "vendor_b": {{
      "vendor_name": "Vendor B Name",
      "pros": [
        "List 3-5 key advantages"
      ],
      "cons": [
        "List 3-5 key disadvantages"
      ],
      "negotiation_strategy": "Single concise sentence about main negotiation approach"
    }},
    "vendor_c": {{
      "vendor_name": "Vendor C Name", 
      "pros": [
        "List 3-5 key advantages"
      ],
      "cons": [
        "List 3-5 key disadvantages"
      ],
      "negotiation_strategy": "Single concise sentence about main negotiation approach"
    }}
  }},
  "recommendation": {{
    "recommended_vendor": "Vendor X",
    "reason": "Brief 1-2 sentence explanation why this vendor is recommended",
    "key_negotiation_points": [
      "Top 3 points to negotiate with recommended vendor"
    ]
  }}
}}

IMPORTANT RULES:
1. Keep each pros/cons item to ONE short sentence
2. Negotiation strategy should be ONE sentence only
3. Focus on the most critical points only
4. Use actual vendor names from the documents
5. Be specific with numbers/prices where relevant
6. Return ONLY valid JSON, no extra text
7. Adapt structure to actual number of vendors (may be 2, 3, or more)

Analyze all {len(state["key_points"])} quotations and create the concise format above.
"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=recommendation_prompt)])
            
            try:
                json_content = response.content.strip()
                if json_content.startswith("```json"):
                    json_content = json_content.replace("```json", "").replace("```", "").strip()
                elif json_content.startswith("```"):
                    json_content = json_content.replace("```", "").strip()
                
                recommendation_json = json.loads(json_content)
                
                recommendation = {
                    "concise_report": recommendation_json,
                    "quotations_analyzed": len(state["key_points"]),
                    "recommendation_timestamp": datetime.now().isoformat()
                }
                
            except json.JSONDecodeError as e:
                print(f"  Warning: JSON parsing failed, using text format: {e}")
                recommendation = {
                    "concise_report": {"raw_response": response.content},
                    "quotations_analyzed": len(state["key_points"]),
                    "recommendation_timestamp": datetime.now().isoformat()
                }
            
            print(f"  Concise recommendation generated")
            
        except Exception as e:
            print(f"  Warning: Error generating recommendation: {e}")
            recommendation = {
                "concise_report": {"error": f"Error generating recommendation: {str(e)}"},
                "quotations_analyzed": len(state["key_points"]),
                "recommendation_timestamp": datetime.now().isoformat()
            }
        
        state["recommendation"] = recommendation
        state["current_step"] = "generate_recommendation"
        
        return state
    
    def save_results(self, state: AgentState) -> AgentState:
        """Save all results to files"""
        print("\nSaving results...")
        
        report = {
            "metadata": {
                "analysis_date": datetime.now().isoformat(),
                "quotations_analyzed": len(state["key_points"]),
                "documents": [kp["file_name"] for kp in state["key_points"]],
                "workflow": "extract_data -> extract_keypoints -> unified_comparison -> recommendation"
            },
            "extracted_key_points": state["key_points"],
            "unified_comparison": state["unified_comparison"],
            "final_recommendation": state["recommendation"]
        }
        
        report_file = os.path.join(RESULTS_FOLDER, "negotiation_report.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"  Saved JSON report: {report_file}")
        
        key_points_file = os.path.join(RESULTS_FOLDER, "key_points.json")
        with open(key_points_file, 'w', encoding='utf-8') as f:
            json.dump(state["key_points"], f, indent=2, ensure_ascii=False)
        
        print(f"  Saved key points: {key_points_file}")
        
        concise_report_file = os.path.join(RESULTS_FOLDER, "concise_report.json")
        with open(concise_report_file, 'w', encoding='utf-8') as f:
            json.dump(state["recommendation"]["concise_report"], f, indent=2, ensure_ascii=False)
        
        print(f"  Saved concise report: {concise_report_file}")
        
        print("\n" + "="*80)
        print("CONCISE NEGOTIATION REPORT - READY FOR DISPLAY")
        print("="*80)
        try:
            concise_data = state["recommendation"]["concise_report"]
            print(json.dumps(concise_data, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Error displaying concise report: {e}")
        print("="*80)
        print("Report is now available for frontend display")
        print("="*80 + "\n")
        
        state["current_step"] = "save_results"
        
        return state
    
    def run(self) -> Dict[str, Any]:
        """Execute the complete workflow"""
        print("\n" + "="*80)
        print("🤖 NEGOTIATIONS AGENT - LICENSE QUOTATION ANALYZER (OPTIMIZED)")
        print("="*80)
        print("\nWorkflow:")
        print("  1. Load Documents")
        print("  2. Extract Content (Multi-method)")
        print("  3. Extract Key Points (Structured - Non-null only)")
        print("  4. Unified Comparison (All Points Together)")
        print("  5. Generate Recommendation")
        print("  6. Save Results")
        print("="*80 + "\n")
        
        initial_state = {
            "documents": [],
            "extracted_data": [],
            "key_points": [],
            "unified_comparison": {},
            "recommendation": {},
            "messages": [],
            "current_step": "start"
        }
        
        try:
            final_state = self.graph.invoke(initial_state)
            
            print("\n" + "="*80)
            print("ANALYSIS COMPLETE")
            print("="*80)
            print(f"\nResults saved in: {RESULTS_FOLDER}/")
            print(f"Quotations analyzed: {len(final_state['key_points'])}")
            print(f"Files generated:")
            print(f"  - concise_report.json (SHORT CONCISE REPORT - Main Output)")
            print(f"  - negotiation_report.json (Complete analysis)")
            print(f"  - key_points.json (Structured key points - non-null only)")
            
            return final_state
            
        except Exception as e:
            print(f"\nError during execution: {e}")
            import traceback
            traceback.print_exc()
            raise


def main():
    """Main execution function"""
    
    print("="*80)
    print("NEGOTIATIONS AGENT - LICENSE QUOTATION ANALYZER (OPTIMIZED)")
    print("="*80)
    print()
    
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found in .env file")
        print("\nPlease create a .env file with:")
        print("GEMINI_API_KEY=your_api_key_here")
        return
    
    print("Gemini API key found")
    
    if not os.path.exists(UPLOADS_FOLDER):
        print(f"\nError: Uploads folder not found: {UPLOADS_FOLDER}")
        print(f"\nPlease create the '{UPLOADS_FOLDER}' folder and add quotation documents.")
        print("Supported format: PDF only")
        return
    
    uploads_path = Path(UPLOADS_FOLDER)
    files = list(uploads_path.iterdir())
    
    if not files:
        print(f"\nWarning: No files found in {UPLOADS_FOLDER} folder")
        print("\nPlease add quotation documents to analyze.")
        print("Supported format: PDF only")
        return
    
    print(f"Found {len(files)} file(s) in uploads folder")
    
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    print(f"Results will be saved to: {RESULTS_FOLDER}/")
    
    print("\n" + "="*80)
    print("Starting analysis...")
    print("="*80 + "\n")
    
    try:
        agent = NegotiationsAgent(api_key=GEMINI_API_KEY)
        final_state = agent.run()
        
        print("\n" + "="*80)
        print("SUCCESS - Analysis completed successfully!")
        print("="*80)
        print(f"\nCheck the {RESULTS_FOLDER}/ folder for detailed results")
        
    except Exception as e:
        print("\n" + "="*80)
        print("FAILED - Analysis encountered an error")
        print("="*80)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


def compare_multiple_quotations(pdf_dir: str = UPLOADS_FOLDER) -> Dict[str, Any]:
    """
    Function to compare multiple quotations from PDFs in a directory.
    This function provides the interface expected by api.py
    
    Args:
        pdf_dir: Directory containing PDF quotation files
        
    Returns:
        Dict containing the analysis results
    """
    try:
        if not GEMINI_API_KEY:
            return {
                "error": "GEMINI_API_KEY not found in environment variables",
                "status": "failed"
            }
        
        if not os.path.exists(pdf_dir):
            return {
                "error": f"Directory not found: {pdf_dir}",
                "status": "failed"
            }
        
        pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
        if not pdf_files:
            return {
                "error": f"No PDF files found in {pdf_dir}",
                "status": "failed"
            }
        
        manage_results_folder()
        
        agent = NegotiationsAgent(api_key=GEMINI_API_KEY)
        final_state = agent.run()
        
        results = {
            "status": "success",
            "quotations_analyzed": len(pdf_files),
            "files_processed": pdf_files
        }
        
        concise_report_path = os.path.join(RESULTS_FOLDER, "concise_report.json")
        if os.path.exists(concise_report_path):
            with open(concise_report_path, 'r', encoding='utf-8') as f:
                results["concise_report"] = json.load(f)
        
        negotiation_report_path = os.path.join(RESULTS_FOLDER, "negotiation_report.json")
        if os.path.exists(negotiation_report_path):
            with open(negotiation_report_path, 'r', encoding='utf-8') as f:
                full_report = json.load(f)
                results["metadata"] = full_report.get("metadata", {})
        
        return results
        
    except Exception as e:
        return {
            "error": f"Analysis failed: {str(e)}",
            "status": "failed"
        }


if __name__ == "__main__":
    main()
