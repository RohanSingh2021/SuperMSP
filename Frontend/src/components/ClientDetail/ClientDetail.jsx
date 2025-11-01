
import React, { useEffect, useState } from "react";
import "./ClientDetail.css";
import AlertCard from "./AlertCard";
import { useNavigate, useLocation } from "react-router-dom";
import SoftwareCard from "./SoftwareCard";
import TicketItem from "./TicketItem";
import ChatbotWidget from "../ChatbotWidget";
import config from '../../config';

const ClientDetail = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const company_id = location.state?.company_id || null;
  const clientName = location.state?.clientName || "Unknown Client";
  const happinessScore = location.state?.happiness_score ?? 0;

  const [softwares, setSoftwares] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [financialData, setFinancialData] = useState(null);
  const [alerts, setAlerts] = useState([]); 

  const handleClose = () => {
    navigate(-1);
  };

  useEffect(() => {
    if (company_id) {
     
      fetch(`${config.API_BASE_URL}/api/clients/${company_id}/softwares`)
        .then((res) => res.json())
        .then((data) => setSoftwares(data))
        .catch((err) => console.error("Software fetch error:", err));

     
      fetch(`${config.API_BASE_URL}/api/clients/${company_id}/tickets`)
        .then((res) => res.json())
        .then((data) => {
          const sortedTickets = data.sort(
            (a, b) => new Date(b.created_at) - new Date(a.created_at)
          );
          setTickets(sortedTickets);
        })
        .catch((err) => console.error("Tickets fetch error:", err));

     
      fetch(`${config.API_BASE_URL}/api/clients/${company_id}/billing-summary`)
        .then((res) => res.json())
        .then((data) => setFinancialData(data))
        .catch((err) => console.error("Financial data fetch error:", err));

     
      fetch(`${config.API_BASE_URL}/api/clients/${company_id}/alerts`)
        .then((res) => res.json())
        .then((data) => setAlerts(data))
        .catch((err) => console.error("Alerts fetch error:", err));
    }
  }, [company_id]);

  return (
    <div className="client-detail-page">
      <div className="close-button">
        <button onClick={handleClose}>← </button>
      </div>

      <div className="client-container">
        <div className="client-header">
          <h2>Client Overview: {clientName}</h2>
          {/* <p>Welcome back! Here’s a snapshot of the client’s performance.</p> */}
        </div>

        <div className="grid-container">
          {/* Left column */}
          <div className="left-column">
            <div className="top-cards-container">
              <div className="card sibyl-score">
                <h3>Tickets Last Month</h3>
                <p className="score-value">{tickets.length}</p>
                <span>tickets</span>
                {/* <p className="subtext">Total tickets raised by this company.</p> */}
              </div>

              <div className="card alerts">
                <h3>Alerts</h3>
                {alerts.length === 0 ? (
                  <p>No alerts</p>
                ) : (
                  alerts.map((alert, i) => (
                    <AlertCard key={i} color={alert.color} message={alert.message} />
                  ))
                )}
              </div>
            </div>

            <div className="card software-licenses">
              <h3>Software Licenses</h3>
              {softwares.length === 0 ? (
                <p>Loading software data...</p>
              ) : (
                softwares.map((sw, i) => (
                  <SoftwareCard
                    key={i}
                    name={sw.name}
                    keyCode={sw.license_type}
                    quantity={sw.count}
                    seats={`${sw.count} users`}
                    color="blue"
                  />
                ))
              )}
            </div>
          </div>

          {/* Right column */}
          <div className="right-column">
            <div className="card happiness-score">
              <h3>Happiness Score</h3>
              <p className="score-big">{happinessScore.toFixed(1)}/5</p>
              <p
                className={`status ${
                  happinessScore >= 4.5
                    ? "excellent"
                    : happinessScore >= 3.5
                    ? "good"
                    : "needs-attention"
                }`}
              >
                {happinessScore >= 4.5
                  ? "Excellent"
                  : happinessScore >= 3.5
                  ? "Good"
                  : "Needs Attention"}
              </p>
            </div>

            <div className="card financial-overview">
              <h3 className="financial-overview-heading">Financial Overview</h3>
              {financialData ? (
                <>
                  <p>
                    <b>Total Billed (YTD):</b>{" "}
                    {financialData.total_billed
                      ? `$${financialData.total_billed.toLocaleString()}`
                      : "N/A"}
                  </p>
                  <p>
                    <b>Outstanding Balance:</b>{" "}
                    <span className="highlight-red">
                      {financialData.outstanding_balance
                        ? `$${financialData.outstanding_balance.toLocaleString()}`
                        : "N/A"}
                    </span>
                  </p>
                  <p>
                    <b>Last Payment:</b> {financialData.last_payment || "N/A"}
                  </p>
                  <p>
                    <b>Next Billing:</b> {financialData.next_billing || "N/A"}
                  </p>
                </>
              ) : (
                <p>Loading financial data...</p>
              )}
            </div>

            <div className="card tickets">
              <h3>Tickets Timeline</h3>
              {tickets.length === 0 ? (
                <p>Loading tickets...</p>
              ) : (
                tickets.map((ticket) => (
                  <TicketItem
                    key={ticket.ticket_id}
                    id={ticket.ticket_id}
                    title={ticket.title}
                    status={ticket.status}
                    priority={ticket.priority}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ✅ Chatbot Widget */}
      <ChatbotWidget />
    </div>
  );
};

export default ClientDetail;
