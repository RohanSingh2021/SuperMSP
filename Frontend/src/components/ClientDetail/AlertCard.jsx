import React from "react";
import "./AlertCard.css";

const AlertCard = ({ color, message }) => {
  return <div className={`alert-card ${color}`}>{message}</div>;
};

export default AlertCard;
