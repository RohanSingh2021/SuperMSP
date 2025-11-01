import React, { useState } from "react";
import "../styles/AgentPersonSuggestionModal.css";
import config from '../config';

const AgentPersonSuggestionModal = ({ isOpen, onClose }) => {
  const [requirement, setRequirement] = useState("");
  const [suggestion, setSuggestion] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    if (!requirement.trim()) return;
  
    setSuggestion([]);
    setLoading(true);
  
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/agent/people/suggest`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ requirement }),
      });
  
      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }
  
      const data = await response.json();
      setSuggestion(data || []);
      document.querySelector(".suggestion-section")?.scrollIntoView({ behavior: "smooth" });
  
    } catch (error) {
      console.error("Error fetching suggestions:", error);
      alert("Failed to fetch suggestions. Please try again.");
    } finally {
      setLoading(false);
    }
  };
  

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <button className="close-btn" onClick={onClose}>×</button>

        {/* Input Section */}
        <div className="upload-section">
          <input
            type="text"
            className="requirement-input"
            placeholder='Specify the type of companies you want to target (e.g., Top IT firms in Bangalore)'
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
          />
          <button className="search-btn" onClick={handleSearch}>Search</button>
        </div>

        {/* API Usage Notice */}
        <div className="api-usage-notice">
          <p style={{ 
            color: "#6b7280", 
            fontSize: "18px", 
            textAlign: "center", 
            margin: "10px 0", 
            fontStyle: "italic"
          }}>
            ⚠️We are using free API keys of SerpAPI which has a limit of 200 searches per month. Please use responsibly.
          </p>
        </div>

        {/* Thinking Section */}
        <div className="thinking-section">
          {loading && <h3>Agent is thinking...</h3>}
          <div className="thinking-image">
              <img
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuA0tX53v5adoJNnfzfF7-mrPT1SJKr-i6hYl14gi9hvhAG0Qh-2LKo8BkwUlcamIG0qQgmdh70bIHKTzLKy_vVbsIZLLqQervL4t1Il9QyTFKq7_T6BnzUae9gkULtTj1rjQwZE-46X_yfmSlJLq15Itnu4kRRNf3i-wrPx9DIDdD2Suji_IFfWS_XwlJWGGpcy7fO1q9FRunNRd08dehAJqoDcJHbd5t1UjzjQy3A2K4ZzevkADvy4qxVnORPmyblwb7LwXhgEBfVQ"
                alt="thinking"
              />
              <div className="gradient-overlay"></div>
            </div>
        </div>

        {/* Suggestion Section */}
        <div className="suggestion-section">
        {suggestion.length > 0 && (<h3 className="suggestion-title">Suggested IT Comapny Contacts</h3>)}
          {suggestion.length > 0 ? (
            suggestion.map((person, index) => (
                <>
                    <div className="suggestion-card" key={index}>
                        <h4 className="company-name">Company: {person.company}</h4>
                        <p className="person-name">Name: {person.name}</p>
                        <p className="person-title">Title: {person.title}</p>
                        <p className="person-linkedin">
                        LinkedIn: <a href={person.linkedin} target="_blank" rel="noreferrer">{person.linkedin}</a>
                        </p>
                    </div>
                </>
            ))
          ) : !loading ? (
            <p style={{ color: "#888", textAlign: "center" }}>No suggestion yet</p>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default AgentPersonSuggestionModal;
