import React from 'react';
import {
  PieChart,
  Pie,
  Tooltip,
  Cell,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const COLORS = [
  "#3B82F6", // blue
  "#14B8A6", // teal
  "#8B5CF6", // violet
  "#FACC15", // yellow
  "#FB923C", // orange
  "#F43F5E", // rose
  "#22C55E", // green
  "#0EA5E9", // sky
  "#64748B"  // gray/others
];

const PieCharts = ({ contractsData, loadingCharts }) => {
  const ticketVolumeData = contractsData.map((c) => ({
    name: c.company_name,
    value: c.total_tickets,
  }));

  const annualRevenueData = contractsData.map((c) => ({
    name: c.company_name,
    value: c.annual_revenue,
  }));

  return (
    <div className="piecharts-section">
      <div className="chart-card">
        <h2>Ticket Volume by Company</h2>
        {loadingCharts ? (
          <p>Loading chart...</p>
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <PieChart>
              <Pie
                data={ticketVolumeData}
                dataKey="value"
                nameKey="name"
                outerRadius={80}
                fill="#8884d8"
                label
              >
                {ticketVolumeData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="chart-card">
        <h2>Annual Revenue by Company</h2>
        {loadingCharts ? (
          <p>Loading chart...</p>
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <PieChart>
              <Pie
                data={annualRevenueData}
                dataKey="value"
                nameKey="name"
                outerRadius={80}
                fill="#82ca9d"
                label
              >
                {annualRevenueData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default React.memo(PieCharts);
