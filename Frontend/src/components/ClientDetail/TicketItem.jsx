import React from "react";
import "./TicketItem.css";

const TicketItem = ({ id, title, status, priority }) => {
  return (
    <div className="ticket-item">
      <div>
        <p className="ticket-title">#{id}: {title}</p>
        <p className="ticket-date">Priority: {priority}</p>
      </div>
      <span className={`ticket-status ${status.toLowerCase().replace(" ", "-")}`}>
        {status}
      </span>
    </div>
  );
};

export default TicketItem;
