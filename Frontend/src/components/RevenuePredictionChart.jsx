
import React from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const RevenuePredictionChart = ({ predictionData, loadingPrediction }) => {
  console.log('RevenuePredictionChart received data:', predictionData);
  console.log('Loading state:', loadingPrediction);
  
  if (loadingPrediction) {
    return <p>Loading revenue predictions...</p>;
  }

  if (!predictionData || predictionData.length === 0) {
    return <p>No prediction data available.</p>;
  }

  
  const processedData = predictionData.map((item, index) => {
    const isPredicted = index === predictionData.length - 1; 
    return {
      ...item,
    
      monthDisplay: new Date(item.month + '-01').toLocaleDateString('en-US', { 
        month: 'short', 
        year: 'numeric' 
      }),
      actualRevenue: isPredicted ? null : item.revenue,
      predictedRevenue: isPredicted ? item.revenue : null,
      actualTickets: isPredicted ? null : item.tickets,
      predictedTickets: isPredicted ? item.tickets : null,
    };
  });

  
  if (processedData.length > 1) {
    const lastActual = processedData[processedData.length - 2];
    const predicted = processedData[processedData.length - 1];
    
    
    predicted.predictedRevenue = predicted.revenue;
    predicted.predictedTickets = predicted.tickets;
    
    lastActual.predictedRevenue = lastActual.revenue;
    lastActual.predictedTickets = lastActual.tickets;
  }

  return (
    <div className="revenue-prediction-section">
      <div className="chart-card">
        <h2>Monthly Revenue (Actual vs Predicted)</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={processedData} margin={{ top: 5, right: 30, left: 20, bottom: 60 }}>
            <XAxis 
              dataKey="monthDisplay" 
              angle={-45}
              textAnchor="end"
              height={80}
              interval={0}
              fontSize={11}
            />
            <YAxis domain={['dataMin - 1000', 'dataMax + 1000']} fontSize={11}/>
            <Tooltip 
              labelFormatter={(label) => `Month: ${label}`}
              formatter={(value, name) => [
                `$${value?.toLocaleString()}`, 
                name
              ]}
            />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="actualRevenue" 
              stroke="#2563eb" 
              name="Actual Revenue"
              connectNulls={false}
              strokeWidth={2}
            />
            <Line 
              type="monotone" 
              dataKey="predictedRevenue" 
              stroke="#2563eb" 
              name="Predicted Revenue"
              connectNulls={false}
              strokeDasharray="5 5"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h2>Monthly Tickets (Actual vs Predicted)</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={processedData} margin={{ top: 5, right: 30, left: 20, bottom: 60 }}>
            <XAxis 
              dataKey="monthDisplay" 
              angle={-45}
              textAnchor="end"
              height={80}
              interval={0}
              fontSize={11}
            />
            <YAxis domain={['dataMin - 10', 'dataMax + 10']} fontSize={11}/>
            <Tooltip 
              labelFormatter={(label) => `Month: ${label}`}
              formatter={(value, name) => [
                `${value?.toLocaleString()} tickets`, 
                name
              ]}
            />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="actualTickets" 
              stroke="#f97316" 
              name="Actual Tickets"
              connectNulls={false}
              strokeWidth={2}
            />
            <Line 
              type="monotone" 
              dataKey="predictedTickets" 
              stroke="#f97316" 
              name="Predicted Tickets"
              connectNulls={false}
              strokeDasharray="5 5"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default React.memo(RevenuePredictionChart);
