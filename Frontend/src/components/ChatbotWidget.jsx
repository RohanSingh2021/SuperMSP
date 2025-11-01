
import React, { useState, useRef, useEffect } from "react";
import "../styles/ChatbotWidget.css";
import config from '../config';

export default function ChatbotWidget({ isOpen, onToggle }) {
  const [messages, setMessages] = useState([
    { type: "bot", text: "Hello! How can I help you today? Type /help for available commands." }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [pendingApproval, setPendingApproval] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const toggleChat = () => onToggle();

  const formatEmailPreview = (emails) => {
    return emails.map((email, idx) => (
      <div key={idx} className="email-preview-item">
        <div className="email-preview-header">
          <strong>To:</strong> {email.to}
          {email.company && <span> ({email.company})</span>}
          {email.recipient && <span> ({email.recipient})</span>}
        </div>
        <div className="email-preview-subject">
          <strong>Subject:</strong> {email.subject}
        </div>
        <div className="email-preview-body">
          <strong>Message:</strong>
          <pre>{email.body}</pre>
        </div>
      </div>
    ));
  };

  const handleDownload = (filename, fileType) => {
    const downloadUrl = `${config.API_BASE_URL}/api/download/${filename}`;
    
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    link.target = '_blank'; 
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleApprove = async () => {
    if (!pendingApproval) return;

    setMessages((prev) => [...prev, { type: "bot", text: "Sending emails..." }]);
    
    try {
      const res = await fetch(`${config.API_BASE_URL}/api/chatbot/approve-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approved: true,
          emails: pendingApproval.emails,
          command: pendingApproval.command
        })
      });

      const data = await res.json();

      setMessages((prev) => prev.filter((msg) => msg.text !== "Sending emails..."));

      if (data.status === "sent") {
        setMessages((prev) => [
          ...prev,
          { 
            type: "bot", 
            text: `✅ ${data.message}\n\nSent: ${data.sent_count}\nFailed: ${data.failed_count}` 
          }
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          { type: "bot", text: `❌ ${data.message}` }
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { type: "bot", text: `Error: ${err.message}` }
      ]);
    } finally {
      setPendingApproval(null);
    }
  };

  const handleReject = () => {
    setMessages((prev) => [
      ...prev,
      { type: "bot", text: "Email sending cancelled." }
    ]);
    setPendingApproval(null);
  };

  const handleSend = async () => {
    if (!inputValue.trim()) return;
  
    setMessages((prev) => [...prev, { type: "user", text: inputValue }]);
    const query = inputValue;
    setInputValue("");
  
    setMessages((prev) => [...prev, { type: "bot", text: "AI is thinking..." }]);
  
    try {
      const res = await fetch(`${config.API_BASE_URL}/api/chatbot/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query })
      });
  
      const data = await res.json();
  
      setMessages((prev) => prev.filter((msg) => msg.text !== "AI is thinking..."));
  
      if (data.error) {
        setMessages((prev) => [...prev, { type: "bot", text: `Error: ${data.error}` }]);
      } else if (data.type === "file_export") {
        if (data.filename) {
          setMessages((prev) => [
            ...prev,
            { 
              type: "bot", 
              text: data.message || `Your ${data.file_type.toUpperCase()} file is ready!`,
              fileDownload: {
                filename: data.filename,
                fileType: data.file_type
              },
              analysisPreview: data.final_response
            }
          ]);
        } else if (data.error) {
          setMessages((prev) => [
            ...prev,
            { type: "bot", text: `❌ ${data.message || data.error}` }
          ]);
        }
      } else if (data.type === "email" && data.requires_approval) {
        const emailPreviews = formatEmailPreview(data.emails);
        
        setMessages((prev) => [
          ...prev,
          { 
            type: "bot", 
            text: data.message,
            emailPreviews: emailPreviews,
            requiresApproval: true
          }
        ]);

        setPendingApproval({
          emails: data.emails,
          command: data.command
        });
      } else if (data.type === "email" && data.status === "error") {
        setMessages((prev) => [...prev, { type: "bot", text: `❌ ${data.message}` }]);
      } else if (data.type === "email" && data.status === "no_data") {
        setMessages((prev) => [...prev, { type: "bot", text: `ℹ️ ${data.message}` }]);
      } else if (data.type === "help") {
        setMessages((prev) => [...prev, { type: "bot", text: data.message }]);
      } else {
        const botText = data.final_response || JSON.stringify(data, null, 2);
        setMessages((prev) => [...prev, { type: "bot", text: botText }]);
      }
    } catch (err) {
      setMessages((prev) => [...prev, { type: "bot", text: `Error: ${err.message}` }]);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleSend();
  };

  return (
    <div className="chatbot-widget">
      {/* Show toggle button only if chatbot is closed */}
      {!isOpen && (
        <button className="chatbot-toggle-btn" onClick={toggleChat}>
          💬
        </button>
      )}

      {isOpen && (
        <div className="chatbot-window">
          <div className="chatbot-header">
            Chat Assistant
            <button className="chatbot-close-btn" onClick={toggleChat}>
              ✖
            </button>
          </div>

          <div className="chatbot-messages">
            {messages.map((msg, idx) => (
              <div key={idx} className={`chat-message ${msg.type}`}>
                <div className="message-text">{msg.text}</div>
                
                {/* File Download Section */}
                {msg.fileDownload && (
                  <div className="file-download-section">
                    <button 
                      className="download-btn"
                      onClick={() => handleDownload(msg.fileDownload.filename, msg.fileDownload.fileType)}
                    >
                      📥 Download {msg.fileDownload.fileType.toUpperCase()} File
                    </button>
                    <div className="file-info">
                      <small>{msg.fileDownload.filename}</small>
                    </div>
                    
                    {/* Optional: Show analysis preview */}
                    {msg.analysisPreview && (
                      <details className="analysis-preview">
                        <summary>View Analysis Summary</summary>
                        <div className="preview-content">
                          {msg.analysisPreview}
                        </div>
                      </details>
                    )}
                  </div>
                )}
                
                {/* Email Preview Section */}
                {msg.emailPreviews && (
                  <div className="email-previews">
                    {msg.emailPreviews}
                  </div>
                )}
                
                {/* Email Approval Buttons */}
                {msg.requiresApproval && idx === messages.length - 1 && (
                  <div className="approval-buttons">
                    <button 
                      className="approve-btn" 
                      onClick={handleApprove}
                      disabled={!pendingApproval}
                    >
                      ✅ Approve & Send
                    </button>
                    <button 
                      className="reject-btn" 
                      onClick={handleReject}
                      disabled={!pendingApproval}
                    >
                      ❌ Cancel
                    </button>
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="chatbot-input">
            <input
              type="text"
              placeholder="Type a message or /help for commands..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={pendingApproval !== null}
            />
            <button 
              onClick={handleSend}
              disabled={pendingApproval !== null}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}