import React, { useState, useEffect } from 'react';
import '../styles/Dashboard.css';
import ChatbotWidget from './ChatbotWidget';
import PieCharts from './PieCharts';
import config from '../config';
import RevenuePredictionChart from "./RevenuePredictionChart";
import useTicketWebSocket from '../hooks/useTicketWebSocket';

const Dashboard = () => {
  const [metrics, setMetrics] = useState({
    totalRevenue: 0,
    pendingRevenue: 0,
    overdueRevenue: 0,
    customerSatisfaction: 0,
    ticketsResolved: 0,
  });
  const [criticalAlertsData, setCriticalAlertsData] = useState({
    amountOverdue: 0,
    lowSatisfactionCustomers: 0,
    licensesExpiring2025: 0,
  });
  const [contractsData, setContractsData] = useState([]); 
  const [loading, setLoading] = useState(true);
  const [loadingCharts, setLoadingCharts] = useState(true);
  const [error, setError] = useState(null);

  const [processingTicket, setProcessingTicket] = useState(false);
  const [systemInitialized, setSystemInitialized] = useState(false);
  const [predictionData, setPredictionData] = useState([]);
  const [loadingPrediction, setLoadingPrediction] = useState(true);

  const { 
    timeline, 
    pendingTickets, 
    connectionStatus, 
    isConnected 
  } = useTicketWebSocket();

  useEffect(() => {
    const initializeSystem = async () => {
      try {
        const response = await fetch(`${config.API_BASE_URL}/api/tickets/initialize`, {
          method: 'POST',
        });
        if (response.ok) {
          setSystemInitialized(true);
          console.log('Ticket system initialized');
        }
      } catch (err) {
        console.error('Failed to initialize ticket system:', err);
      }
    };
    initializeSystem();
  }, []);

  

  useEffect(() => {
    const fetchRevenuePrediction = async () => {
      try {
        const response = await fetch(`${config.API_BASE_URL}/api/revenue-prediction`);
        if (!response.ok) throw new Error('Failed to fetch revenue predictions');
        const data = await response.json();
  
        const chartData = data.data.map((item) => ({
          month: item.month,
          revenue: item.revenue,             
          tickets: item.tickets,             
        }));
  
        setPredictionData(chartData);
        console.log('Revenue prediction data loaded:', chartData);
      } catch (error) {
        console.error('Error fetching revenue prediction data:', error);
      } finally {
        setLoadingPrediction(false);
      }
    };
  
    fetchRevenuePrediction();
  }, []);


  const handleSendTicket = async () => {
    if (processingTicket) return;
    
    setProcessingTicket(true);
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/tickets/send`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log('Ticket sent:', result);
      } else {
        const error = await response.json();
        console.error('Failed to send ticket:', error);
      }
    } catch (err) {
      console.error('Error sending ticket:', err);
    } finally {
      setProcessingTicket(false);
    }
  };

  const handleTicketApproval = async (ticketId, approved) => {
    try {
      const response = await fetch(`${config.API_BASE_URL}/api/tickets/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ticket_id: ticketId,
          approved: approved,
        }),
      });

      if (response.ok) {
        console.log(`Ticket ${ticketId} ${approved ? 'approved' : 'rejected'}`);
      } else {
        const error = await response.json();
        console.error('Failed to process approval:', error);
      }
    } catch (err) {
      console.error('Error processing approval:', err);
    }
  };

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        setLoading(true);

        const metricsResponse = await fetch(`${config.API_BASE_URL}/api/dashboard/metrics`);
        if (!metricsResponse.ok) throw new Error(`HTTP error! status: ${metricsResponse.status}`);
        const metricsData = await metricsResponse.json();
        setMetrics({
          totalRevenue: metricsData.total_revenue,
          pendingRevenue: metricsData.pending_revenue,
          overdueRevenue: metricsData.overdue_revenue,
          customerSatisfaction: metricsData.customer_satisfaction,
          ticketsResolved: metricsData.tickets_resolved,
        });

        const alertsResponse = await fetch(`${config.API_BASE_URL}/api/dashboard/critical-alerts`);
        if (!alertsResponse.ok) throw new Error(`HTTP error! status: ${alertsResponse.status}`);
        const alertsData = await alertsResponse.json();
        setCriticalAlertsData({
          amountOverdue: alertsData.amount_overdue,
          lowSatisfactionCustomers: alertsData.low_satisfaction_customers,
          licensesExpiring2025: alertsData.licenses_expiring_2025,
        });

        setError(null);
      } catch (err) {
        console.error('Error fetching metrics:', err);
        setError('Failed to load metrics. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchCompanyContracts = async () => {
      try {
        const response = await fetch(`${config.API_BASE_URL}/api/dashboard/company-contracts`);
        if (!response.ok) throw new Error('Failed to fetch company contracts');
        const data = await response.json();
        setContractsData(data);
      } catch (err) {
        console.error('Error fetching company contracts:', err);
      } finally {
        setLoadingCharts(false);
      }
    };
    fetchCompanyContracts();
  }, []);

  const formatCurrency = (amount) => {
    if (amount >= 1000000) {
      return `$${(amount / 1000000).toFixed(1)}M`;
    } else if (amount >= 1000) {
      return `$${(amount / 1000).toFixed(1)}K`;
    }
    return `$${amount.toFixed(0)}`;
  };

  const criticalAlerts = [
    {
      icon: '💳',
      type: 'payment',
      message: `Payment overdue: $${criticalAlertsData.amountOverdue.toLocaleString()} total amount due.`,
    },
    {
      icon: '😞',
      type: 'satisfaction',
      message: `${criticalAlertsData.lowSatisfactionCustomers} customers identified with low satisfaction scores.`,
    },
    {
      icon: '⚠️',
      type: 'license',
      message: `${criticalAlertsData.licensesExpiring2025} software licenses expiring in 2025.`,
    },
  ];

  const COLORS = ['#60a5fa', '#fbbf24', '#10b981', '#ef4444', '#6366f1', '#f97316', '#14b8a6', '#84cc16', '#e11d48', '#3b82f6'];

  return (
    <div className="dashboard-container">
      <div className="dashboard-content">
        <div className="dashboard-header">
          <h1>Dashboard</h1>
          <p className="dashboard-subtitle">Smart Ticket Assignment System - MSP</p>
          {/* WebSocket Connection Status */}
          <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            <span className="status-indicator"></span>
            <span className="status-text">
              {connectionStatus === 'Connected' ? 'Real-time updates active' : `Connection: ${connectionStatus}`}
            </span>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {/* Top Metrics Cards */}
        <div className="metrics-cards">
          <div className="metric-card">
            <div className="metric-label">MONTHLY REVENUE</div>
            <div className="metric-value">
              {loading ? 'Loading...' : (
                <div className="revenue-breakdown">
                  <div className="revenue-item paid">
                    <span className="revenue-label">Paid:</span>
                    <span className="revenue-amount">{formatCurrency(metrics.totalRevenue)}</span>
                  </div>
                  <div className="revenue-item pending">
                    <span className="revenue-label">Pending:</span>
                    <span className="revenue-amount">{formatCurrency(metrics.pendingRevenue)}</span>
                  </div>
                  <div className="revenue-item overdue">
                    <span className="revenue-label">Overdue:</span>
                    <span className="revenue-amount">{formatCurrency(metrics.overdueRevenue)}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">AVG. Customer Satisfaction</div>
            <div className="metric-value">
              {loading ? 'Loading...' : `${metrics.customerSatisfaction.toFixed(1)}/5`}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Tickets Resolved LAST Month</div>
            <div className="metric-value">
              {loading ? 'Loading...' : metrics.ticketsResolved.toLocaleString()}
            </div>
          </div>
        </div>

        <RevenuePredictionChart predictionData={predictionData} loadingPrediction={loadingPrediction} />

        {/* Main Content Grid */}
        <div className="content-grid">
          {/* Left Column - Ticket Timeline Section */}
          <div className="left-column">
            <div className="section ticket-timeline">
              <div className="section-header">
                <h2>Ticket Processing Timeline</h2>
                <button 
                  className={`send-ticket-btn ${processingTicket ? 'processing' : ''}`}
                  onClick={handleSendTicket}
                  disabled={processingTicket || !systemInitialized}
                >
                  {processingTicket ? 'Processing...' : 'Send Ticket'}
                </button>
              </div>
              
              <div className="timeline-container">
                {timeline.length === 0 ? (
                  <div className="no-tickets">
                    <p>No tickets processed yet. Click "Send Ticket" to start processing.</p>
                  </div>
                ) : (
                  <div className="timeline-list">
                    {timeline.map((entry, index) => (
                      <div key={index} className={`timeline-entry ${entry.status}`}>
                        <div className="timeline-header">
                          <h4>Ticket {entry.ticket_id}: {entry.title}</h4>
                          <span className={`status-badge ${entry.status}`}>
                            {entry.status.replace('_', ' ').toUpperCase()}
                          </span>
                        </div>
                        <div className="timeline-steps">
                          {entry.steps.map((step, stepIndex) => (
                            <div key={stepIndex} className="timeline-step">
                              <span className="step-icon">•</span>
                              <span className="step-text">{step}</span>
                            </div>
                          ))}
                        </div>
                        {entry.assigned_technician && (
                          <div className="assigned-technician">
                            <strong>Assigned to:</strong> {entry.assigned_technician.name} 
                            <span className="technician-specialization">
                              ({entry.assigned_technician.specialization})
                            </span>
                            <br />
                            <span className="technician-email">{entry.assigned_technician.email}</span>
                          </div>
                        )}
                        {entry.rag_answer && (
                          <div className="rag-answer">
                            <strong>RAG Answer:</strong> {entry.rag_answer}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Pending Approval and Critical Alerts */}
          <div className="right-column">
            {/* Pending Approval Section */}
            <div className="section pending-approval">
              <h2>Pending Human Approval</h2>
              {pendingTickets.length === 0 ? (
                <div className="no-pending">
                  <p>No tickets pending approval.</p>
                </div>
              ) : (
                <div className="pending-tickets-list">
                  {pendingTickets.map((ticket, index) => (
                    <div key={index} className="pending-ticket">
                      <div className="ticket-info">
                        <h4>Ticket {ticket.ticket_id}: {ticket.title}</h4>
                        <p className="ticket-description">{ticket.description}</p>
                        {ticket.rag_answer && (
                          <div className="rag-answer">
                            <strong>Suggested Answer:</strong> {ticket.rag_answer}
                          </div>
                        )}
                      </div>
                      <div className="approval-actions">
                        <button 
                          className="approve-btn"
                          onClick={() => handleTicketApproval(ticket.ticket_id, true)}
                        >
                          Approve
                        </button>
                        <button 
                          className="reject-btn"
                          onClick={() => handleTicketApproval(ticket.ticket_id, false)}
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Critical Alerts */}
            <div className="section critical-alerts">
              <h2>Critical Alerts</h2>
              <div className="alerts-list">
                {criticalAlerts.map((alert, index) => (
                  <div key={index} className={`alert-item ${alert.type}`}>
                    <span className="alert-icon">{alert.icon}</span>
                    <span className="alert-message">{alert.message}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ==================== PIE CHART SECTION ==================== */}
        <PieCharts contractsData={contractsData} loadingCharts={loadingCharts} />

      </div>

      <ChatbotWidget />
    </div>
  );
};

export default Dashboard;
