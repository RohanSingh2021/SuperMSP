
import React, { useState, useEffect } from "react";
import "../styles/AgentUploadModel.css";
import config from '../config';

const AgentUploadModal = ({ isOpen, onClose }) => {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false); 
  const [response, setResponse] = useState(null);
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState(null);

  const handleFileChange = (e) => {
    setFiles([...e.target.files]);
    setError(null);
  };

  const pollStatus = async () => {
    try {
      const res = await fetch(`${config.API_BASE_URL}/api/agent/status`);
      const statusData = await res.json();
      setStatus(statusData.status);
      setProgress(statusData.progress || statusData.message);
      
      if (statusData.status === "completed") {
        setResponse(statusData.results);
        setLoading(false);
        return true; 
      } else if (statusData.status === "error") {
        setError(statusData.message);
        setLoading(false);
        return true; 
      }
      return false; 
    } catch (err) {
      setError("Failed to check analysis status");
      setLoading(false);
      return true; 
    }
  };

  const handleUploadClick = async () => {
    if (files.length === 0) {
      setError("Please select at least one PDF file");
      return;
    }

  
    const invalidFiles = files.filter(file => !file.name.toLowerCase().endsWith('.pdf'));
    if (invalidFiles.length > 0) {
      setError(`Only PDF files are supported. Invalid files: ${invalidFiles.map(f => f.name).join(', ')}`);
      return;
    }
  
    setLoading(true);
    setResponse(null);
    setError(null);
    setStatus("uploading");
    setProgress("");
  
    try {
      const formData = new FormData();
      files.forEach(file => formData.append("files", file));
  
      const res = await fetch(`${config.API_BASE_URL}/api/agent/upload`, {
        method: "POST",
        body: formData
      });
  
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      const data = await res.json();
      setProgress("Files uploaded successfully. Starting analysis...");
      
      const pollInterval = setInterval(async () => {
        const shouldStop = await pollStatus();
        if (shouldStop) {
          clearInterval(pollInterval);
        }
      }, 2000); 

    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleReset = async () => {
    try {
      await fetch(`${config.API_BASE_URL}/api/agent/reset`, { method: "POST" });
      setFiles([]);
      setResponse(null);
      setStatus(null);
      setProgress("");
      setError(null);
      setLoading(false);
    } catch (err) {
      setError("Failed to reset analysis");
    }
  };


  useEffect(() => {
    if (!isOpen) {
      setFiles([]);
      setResponse(null);
      setStatus(null);
      setProgress("");
      setError(null);
      setLoading(false);
    }
  }, [isOpen]);

  const renderResults = () => {
    if (!response || !response.concise_report) return null;

    const report = response.concise_report;
    
    return (
      <div className="results-section">
        <h3>📊 Negotiation Analysis Results</h3>
        
        {/* Vendor Analysis */}
        {report.vendor_analysis && (
          <div className="vendor-analysis">
            <h4>Vendor Comparison</h4>
            {Object.entries(report.vendor_analysis).map(([key, vendor]) => (
              <div key={key} className="vendor-card">
                <h5>{vendor.vendor_name}</h5>
                
                <div className="pros-cons">
                  <div className="pros">
                    <strong>✅ Pros:</strong>
                    <ul>
                      {vendor.pros?.map((pro, idx) => (
                        <li key={idx}>{pro}</li>
                      ))}
                    </ul>
                  </div>
                  
                  <div className="cons">
                    <strong>❌ Cons:</strong>
                    <ul>
                      {vendor.cons?.map((con, idx) => (
                        <li key={idx}>{con}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                
                {vendor.negotiation_strategy && (
                  <div className="negotiation-strategy">
                    <strong>💡 Negotiation Strategy:</strong>
                    <p>{vendor.negotiation_strategy}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Recommendation */}
        {report.recommendation && (
          <div className="recommendation">
            <h4>🏆 Final Recommendation</h4>
            <div className="recommended-vendor">
              <strong>Recommended Vendor:</strong> {report.recommendation.recommended_vendor}
            </div>
            <div className="reason">
              <strong>Reason:</strong> {report.recommendation.reason}
            </div>
            {report.recommendation.key_negotiation_points && (
              <div className="key-points">
                <strong>Key Negotiation Points:</strong>
                <ul>
                  {report.recommendation.key_negotiation_points.map((point, idx) => (
                    <li key={idx}>{point}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <button className="reset-btn" onClick={handleReset}>
          Start New Analysis
        </button>
      </div>
    );
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <button className="close-btn" onClick={onClose}>
          ×
        </button>

        <div className="upload-section">
          <label className="upload-btn">
            <span className="material-symbols-outlined upload-icon">
              upload_file
            </span>
            <p>UPLOAD PDF FILES</p>
            <input
              type="file"
              multiple
              accept=".pdf"
              onChange={handleFileChange}
              style={{ display: "none" }}
            />
          </label>
          
          {files.length > 0 && (
            <div className="selected-files">
              <h4>Selected Files:</h4>
              <ul>
                {files.map((file, idx) => (
                  <li key={idx}>{file.name}</li>
                ))}
              </ul>
            </div>
          )}
          
          <button 
            className="confirm-upload" 
            onClick={handleUploadClick}
            disabled={loading || files.length === 0}
          >
            {loading ? "Processing..." : "Run Negotiation Analysis"}
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="error-section">
            <h4>❌ Error</h4>
            <p>{error}</p>
          </div>
        )}

        {/* Progress Display */}
        {loading && (
          <div className="thinking-section">
            <h3>🤖 Negotiation Agent Processing</h3>
            <div className="loading-message">
              <p className="main-message">
                The Negotiation Agent is working on several steps right now. Sit tight — it might take a little while to finish everything!
              </p>
              <p className="progress-text">{progress}</p>
            </div>
            <div className="thinking-image">
              <img
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuA0tX53v5adoJNnfzfF7-mrPT1SJKr-i6hYl14gi9hvhAG0Qh-2LKo8BkwUlcamIG0qQgmdh70bIHKTzLKy_vVbsIZLLqQervL4t1Il9QyTFKq7_T6BnzUae9gkULtTj1rjQwZE-46X_yfmSlJLq15Itnu4kRRNf3i-wrPx9DIDdD2Suji_IFfWS_XwlJWGGpcy7fO1q9FRunNRd08dehAJqoDcJHbd5t1UjzjQy3A2K4ZzevkADvy4qxVnORPmyblwb7LwXhgEBfVQ"
                alt="thinking"
              />
              <div className="gradient-overlay"></div>
            </div>
          </div>
        )}

        {/* Results Display */}
        {renderResults()}
      </div>
    </div>
  );
};

export default AgentUploadModal;
