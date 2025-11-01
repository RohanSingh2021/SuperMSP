import React from "react";
import "./SoftwareCard.css";

const SoftwareCard = ({ name, keyCode, quantity, seats, color }) => {

  const calculateWidth = () => {
    return '100%'; 
  };

  return (
    <div className="software-card">
      <div className="software-info">
        <p className="software-name">{name}</p>
        <p className="license-key">{keyCode}</p>
        <p className="expiry">No. of softwares used: {quantity}</p>
      </div>
      <div className="seats-bar">
        <div 
          className={`bar-fill ${color}`} 
          style={{ width: calculateWidth() }}
        ></div>
        <p className="seat-count">{seats}</p>
      </div>
    </div>
  );
};

export default SoftwareCard;
