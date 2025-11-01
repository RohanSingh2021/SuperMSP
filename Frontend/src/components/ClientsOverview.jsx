import React, { useState } from "react";
import "../styles/ClientsOverview.css";
import ClientCard from "./ClientCard";
import { useEffect } from "react";
import ChatbotWidget from "./ChatbotWidget";
import config from '../config';

function ClientsOverview() {
  const [searchTerm, setSearchTerm] = useState("");
  const [clients, setClients] = useState([]);
  const [stats, setStats] = useState({});
  const colors = [
    "#f4ffb4", "#47d7ac", "#bdbb7a", "#a0f2f2",
    "#d3bba7", "#9bf0f0", "#ffb47a", "#64f2b5",
    "#4ce1af", "#ffb7b7", "#64e1f7", "#ff9f40"
  ];

  useEffect(() => {
    fetch(`${config.API_BASE_URL}/api/clients/allClients`)
      .then(res => res.json())
      .then(data => {
        console.log("Clients API response:", data); 
        setClients(data);
      })
      .catch(err => console.error(err));

      fetch(`${config.API_BASE_URL}/api/clients/stats`)
      .then(res => res.json())
      .then(stats => setStats(stats))
      .catch(err => console.error(err));
  }, []);
  

  const filteredClients = clients.filter(client =>
    client.company_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="clients-page">
      <div className="overview-header">
        <div className="header-left">
          <h1>All Clients Overview</h1>
          {/* <p>Live holographic projections of client data streams.</p> */}
        </div>
        <div className="header-right">
          <input
            type="text"
            placeholder="Search clients..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="client-search-input"
          />
        </div>
      </div>

      <div className="stats-section">
        <div className="stat-card">
          <h3>Total Active Clients</h3>
          <p className="value">{stats.active_companies_count}</p>
        </div>

        <div className="stat-card">
          <h3>Avg Happiness Score</h3>
          <p className="value">{stats.average_happiness_score}/5</p>
        </div>

        <div className="stat-card">
          <h3>Overall Ticket Volume</h3>
          <p className="value">{stats.total_tickets_raised}</p>
        </div>
      </div>

      <h2 className="client-section-title">Client Data Streams</h2>
      <p className="client-instruction-text">Click on a client's name to view detailed information.</p>

      <div className="client-grid">
        {filteredClients.map((client, i) => (
          <ClientCard key={client.company_id} id={client.company_id} name={client.company_name} happiness_score={client.happiness_score} logoColor={colors[i % colors.length]} />
        ))}
      </div>
      <ChatbotWidget />
    </div>
  );
}

export default ClientsOverview;
