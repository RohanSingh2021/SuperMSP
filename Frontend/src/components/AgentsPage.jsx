import React, { useState } from "react";
import "../styles/AgentsPage.css";
import AgentUploadModal from "./AgentUploadModal";
import AgentSoftwareSuggestionModal from "./AgentSoftwareSuggestionModal";
import AgentPersonSuggestionModal from "./AgentPersonSuggestionModal";
import AgentContractRevisionModal from "./AgentContractRevisionModal"; 
import ChatbotWidget from "./ChatbotWidget"; 



const agentsData = [
  {
    name: "Software Suggestion",
    icon: "",
    image: "/software-suggestion.png",
    color: "green",
    progress: 75,
    description: "Analyzing requirements..."
  },
  {
    name: "Negotiation",
    icon: "",
    image: "/negotiation.png",
    color: "amber",
    progress: 50,
    description: "Optimizing terms..."
  },
  {
    name: "Customer Outreach",
    icon: "",
    image: "/customer-discovery.png",
    color: "blue",
    progress: 90,
    description: "Assisting users..."
  },
  {
    name: "Contract Price Revision",
    icon: "",
    image: "/contract-price-revision.png",
    color: "purple",
    progress: 30,
    description: "Processing revision..."
  }
];

const activityFeed = [
  {
    title: "Suggests new software for client",
    subtitle: "Software Suggestion Agent",
    color: "green",
    progress: 100,
    icon: "",
    image: "/software-suggestion.png"
  },
  {
    title: "Negotiats contract terms with vendor",
    subtitle: "Negotiation Agent",
    color: "amber",
    progress: 80,
    icon: "",
    image: "/negotiation.png"
  },
  {
    title: "Provides linkedin profiles of companies IT heads for outreach",
    subtitle: "Customer Outreach Agent",
    color: "blue",
    progress: 60,
    icon: "",
    image: "/customer-discovery.png"
  },
  {
    title: "Revises contract pricing for clients",
    subtitle: "Contract Price Revision Agent",
    color: "purple",
    progress: 30,
    icon: "",
    image: "/contract-price-revision.png"
  }
];

export default function AgentsPage() {
  const [isNegotiationModalOpen, setIsNegotiationModalOpen] = useState(false);
  const [isSoftwareSuggestionModalOpen, setIsSoftwareSuggestionModalOpen] = useState(false);
  const [isPersonSuggestionModalOpen, setIsPersonSuggestionModalOpen] = useState(false);
  const [isContractRevisionModalOpen, setIsContractRevisionModalOpen] = useState(false); 

  const handleCardClick = (agent) => {
    if (agent.name === "Negotiation") {
      setIsNegotiationModalOpen(true);
    } else if (agent.name === "Software Suggestion") {
      setIsSoftwareSuggestionModalOpen(true);
    } else if (agent.name === "Customer Outreach") {
      setIsPersonSuggestionModalOpen(true);
    } else if (agent.name === "Contract Price Revision") { 
      setIsContractRevisionModalOpen(true);
    }
  };

  return (
    <div className="agents-page">
      <main>
        <section className="agents-overview">
          <h1>Agents Overview</h1>
          <div className="agents-grid">
            {agentsData.map((agent) => (
              <div
                key={agent.name}
                className={`agent-card pulse-${agent.color}`}
                onClick={() => handleCardClick(agent)}
                style={{ cursor: "pointer" }}
              >
                <div className="gradient-overlay"></div>
                <div className="agent-content">
                  <div className="agent-header">
                    <div className={`icon-circle ${agent.color}`}>
                      <img 
                        src={agent.image} 
                        alt={agent.name}
                        className="agent-image"
                      />
                    </div>
                    <h2>{agent.name}</h2>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ✅ Modals */}
        <AgentUploadModal
          isOpen={isNegotiationModalOpen}
          onClose={() => setIsNegotiationModalOpen(false)}
        />
        <AgentSoftwareSuggestionModal
          isOpen={isSoftwareSuggestionModalOpen}
          onClose={() => setIsSoftwareSuggestionModalOpen(false)}
        />
        <AgentPersonSuggestionModal
          isOpen={isPersonSuggestionModalOpen}
          onClose={() => setIsPersonSuggestionModalOpen(false)}
        />
        <AgentContractRevisionModal
          isOpen={isContractRevisionModalOpen} 
          onClose={() => setIsContractRevisionModalOpen(false)}
        />

        <section className="activity-feed">
          <h2 style={{ textAlign: "left", marginLeft: 0 }}>Agents Description</h2>
          {activityFeed.map((item, idx) => (
            <div key={idx} className="activity-item">
              <div className={`activity-icon ${item.color}`}>
                <img 
                  src={item.image} 
                  alt={item.subtitle}
                  className="activity-agent-image"
                />
              </div>
              <div
                className="activity-text"
                style={{ display: "flex", flexDirection: "column", gap: "0.02rem" }}
              >
                <p className="title">{item.title}</p>
                <p className="subtitle">{item.subtitle}</p>
              </div>
              {/* <div className="activity-progress" style={{ marginLeft: "auto" }}>
                <div
                  style={{ width: `${item.progress}%` }}
                  className={`progress-fill ${item.color}`}
                ></div>
              </div> */}
            </div>
          ))}
        </section>
      </main>
      <ChatbotWidget />
    </div>
  );
}
