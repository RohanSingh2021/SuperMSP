import React from "react";
import { useNavigate } from "react-router-dom";
import "../styles/ClientCard.css";

function ClientCard({ id, name, happiness_score, logoColor }) {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate("/client-detail", {
      state: {
        company_id: id,           
        clientName: name,
        happiness_score: happiness_score
      }
    });
  };

  return (
    <div
      className="client-card"
      style={{ boxShadow: `0 0 25px ${logoColor}` }}
    >
      <div
        className="client-logo"
        style={{ background: logoColor }}
        onClick={handleClick}
      >
        <span>{name}</span>
      </div>
    </div>
  );
}

export default ClientCard;
