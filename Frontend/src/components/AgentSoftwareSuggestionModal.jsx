import React, { useState } from "react";
import "../styles/AgentSoftwareSuggestionModal.css";

import config from "../config.js";


const AgentSoftwareSuggestionModal = ({ isOpen, onClose }) => {
  const [requirement, setRequirement] = useState("");
  const [suggestions, setSuggestions] = useState([]); 
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    if (!requirement.trim()) return;

    setSuggestions([]);
    setLoading(true);

    try {
      const response = await fetch(`${config.API_BASE_URL}/api/agent/software/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requirement }),
      });

      const data = await response.json();

      
      const recs = data.recommendations?.recommendations || [];
      setSuggestions(recs);

      
      document.querySelector(".suggestion-section")?.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      console.error("Error fetching software recommendations:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <button className="close-btn" onClick={onClose}>
          ×
        </button>

        {/* Input Section */}
        <div className="upload-section">
          <input
            type="text"
            className="requirement-input"
            placeholder='Enter your software requirements (e.g., “Mailing automation for a team of 10")'
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
          />
          <button className="search-btn" onClick={handleSearch}>
            Search
          </button>
        </div>

        {/* Thinking Section */}
          <div className="thinking-section">
          {loading && (<h3>Agent is thinking...</h3>)}
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
          {suggestions.length > 0 ? (
            <>
              <h3 className="suggestion-title">Best Software Suggestion</h3>
              {suggestions.map((s, i) => (
                <div key={i} className="suggestion-card" style={{textAlign: "center"}}>
                  <h4 className="software-name">{s.name || "N/A"}</h4>
                  <p className="reason-text">{s.reason || "No reason provided"}</p>
                  <p className="pricing-text">Pricing : {s.price || "Not mentioned"}</p>
                  {/* {s.link && (
                    <a href={s.link} target="_blank" rel="noopener noreferrer">
                      Learn more
                    </a>
                  )} */}
                </div>
              ))}
            </>
          ) : !loading ? (
            <p style={{ color: "#888", textAlign: "center" }}>No suggestion yet</p>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default AgentSoftwareSuggestionModal;
