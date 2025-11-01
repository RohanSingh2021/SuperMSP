
import React, { useState, useEffect } from "react";
import "../styles/AgentContractRevisionModal.css";
import config from '../config';

const AgentContractRevisionModal = ({ isOpen, onClose }) => {
  const [companies, setCompanies] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);

 
  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      setError(null);

      fetch(`${config.API_BASE_URL}/api/clients/allClients`)
        .then((res) => {
          if (!res.ok) throw new Error("Failed to fetch companies");
          return res.json();
        })
        .then((data) => {
          setCompanies(data);
          setLoading(false);
        })
        .catch((err) => {
          console.error(err);
          setError("Error fetching company list.");
          setLoading(false);
        });
    }
  }, [isOpen]);


  const handleCompanyClick = (company) => {
    setSearch("");
    setResponse(null);
    setLoading(true);
    setError(null);

    fetch(`${config.API_BASE_URL}/api/price-revision/${company.company_id}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch revision details");
        return res.json();
      })
      .then((data) => {
   
        setTimeout(() => {
          setResponse({
            ...data,
            company_name: company.company_name,
          });
          setLoading(false);
        }, 1000);
      })
      .catch((err) => {
        console.error(err);
        setError("Error fetching revision details.");
        setLoading(false);
      });
  };

  if (!isOpen) return null;

  const filteredCompanies = companies.filter((c) =>
    c.company_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        {/* Close button */}
        <button className="close-btn" onClick={onClose}>
          ×
        </button>

        {/* Company Search & List */}
        <div className="company-list-section">
          <input
            type="text"
            className="company-search"
            placeholder="Search companies..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <ul className="company-list">
            {filteredCompanies.map((c) => (
              <li
                key={c.company_id}
                className="company-item"
                onClick={() => handleCompanyClick(c)}
              >
                {c.company_name}
              </li>
            ))}
          </ul>
          {!loading && filteredCompanies.length === 0 && (
            <p style={{ color: "#888", textAlign: "center" }}>
              No companies found
            </p>
          )}
        </div>

        {/* Loading / Thinking Animation */}
        {loading && (
          <div className="thinking-section">
            <h3>Agent is thinking...</h3>
            <div className="thinking-image">
              <img
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuA0tX53v5adoJNnfzfF7-mrPT1SJKr-i6hYl14gi9hvhAG0Qh-2LKo8BkwUlcamIG0qQgmdh70bIHKTzLKy_vVbsIZLLqQervL4t1Il9QyTFKq7_T6BnzUae9gkULtTj1rjQwZE-46X_yfmSlJLq15Itnu4kRRNf3i-wrPx9DIDdD2Suji_IFfWS_XwlJWGGpcy7fO1q9FRunNRd08dehAJqoDcJHbd5t1UjzjQy3A2K4ZzevkADvy4qxVnORPmyblwb7LwXhgEBfVQ"
                alt="thinking"
              />
              <div className="gradient-overlay"></div>
            </div>
          </div>
        )}

        {/* Error Section */}
        {error && (
          <div style={{ color: "red", textAlign: "center", marginTop: "1rem" }}>
            {error}
          </div>
        )}

        {/* Response Display */}
        {response && !loading && (
          <div className="suggestion-section">
            <h3 className="suggestion-title">
              Price Revision for {response.company_name}
            </h3>
            <div className="suggestion-card">
              <p>
                <strong>Revision Percentage:</strong>{" "}
                {response.revision_percentage}
              </p>
              <p>
                <strong>Revised Monthly Cost:</strong> $
                {response.revised_monthly_cost.toLocaleString()}
              </p>
              <p>
                <strong>Annual Cost Change:</strong> $
                {response.annual_cost_change.toLocaleString()}
              </p>
            </div>
          </div>
        )}

        {/* Default message */}
        {!response && !loading && filteredCompanies.length > 0 && (
          <p style={{ color: "#888", textAlign: "center" }}>
            Click on a company to see the revision results.
          </p>
        )}
      </div>
    </div>
  );
};

export default AgentContractRevisionModal;
