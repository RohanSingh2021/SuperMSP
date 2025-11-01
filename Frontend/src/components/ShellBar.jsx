import React from "react";
import { Link, useLocation } from "react-router-dom";
import "../styles/ShellBar.css";
import ChatbotWidget from "./ChatbotWidget";

function ShellBar({ onChatToggle }) {
  const location = useLocation();

  return (
    <header className="shellbar">
      <Link to="/" className="logo">
        <span className="logo-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" fill="currentColor"/>
            <path d="M12 6c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm0 10c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4z" fill="currentColor"/>
          </svg>
        </span>
        <span className="logo-text">Super MSP</span>
      </Link>

      <nav className="nav-links">
        <Link to="/" className={location.pathname === "/" ? "active" : ""}>Dashboard</Link>
        <Link to="/clients" className={location.pathname === "/clients" ? "active" : ""}>Clients</Link>
        <Link to="/agents" className={location.pathname === "/agents" ? "active" : ""}>Agents</Link>
        <div className="chat-btn-container">
          <button className="chat-ai-btn" onClick={onChatToggle}>
            Chat with AI
          </button>
        </div>
      </nav>

      {/* <div className="search-bar">
        <div className="user-avatar">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z" fill="#9ca3af"/>
          </svg>
        </div>
      </div> */}
    </header>
  );
}

export default ShellBar;
