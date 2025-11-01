import { useState, useEffect, useRef } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import config from '../config';

const useTicketWebSocket = () => {
  const [timeline, setTimeline] = useState([]);
  const [pendingTickets, setPendingTickets] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('Connecting');
  const [lastMessage, setLastMessage] = useState(null);


  const socketUrl = config.API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/tickets';

  const { sendMessage, lastJsonMessage, readyState } = useWebSocket(socketUrl, {
    onOpen: () => {
      console.log('WebSocket connection opened');
      setConnectionStatus('Connected');
    },
    onClose: () => {
      console.log('WebSocket connection closed');
      setConnectionStatus('Disconnected');
    },
    onError: (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('Error');
    },
    shouldReconnect: (closeEvent) => {
      
      console.log('WebSocket attempting to reconnect...');
      return true;
    },
    reconnectAttempts: 10,
    reconnectInterval: 3000,
  });

  
  useEffect(() => {
    if (lastJsonMessage) {
      console.log('Received WebSocket message:', lastJsonMessage);
      setLastMessage(lastJsonMessage);

      const { type, timeline: newTimeline, pending_tickets: newPendingTickets } = lastJsonMessage;

      switch (type) {
        case 'initial_data':
          if (newTimeline) setTimeline(newTimeline);
          if (newPendingTickets) setPendingTickets(newPendingTickets);
          break;

        case 'timeline_update':
          if (newTimeline) {
            setTimeline(newTimeline);
            console.log('Timeline updated via WebSocket');
          }
          break;

        case 'pending_tickets_update':
          if (newPendingTickets) {
            setPendingTickets(newPendingTickets);
            console.log('Pending tickets updated via WebSocket');
          }
          break;

        case 'ticket_update':
         
          console.log('Ticket update received:', lastJsonMessage.data);
          break;

        case 'connection_established':
          console.log('WebSocket connection established:', lastJsonMessage.client_id);
          break;

        case 'error':
          console.error('WebSocket error message:', lastJsonMessage.message);
          break;

        default:
          console.log('Unknown message type:', type);
      }
    }
  }, [lastJsonMessage]);

  
  useEffect(() => {
    const connectionStatusMap = {
      [ReadyState.CONNECTING]: 'Connecting',
      [ReadyState.OPEN]: 'Connected',
      [ReadyState.CLOSING]: 'Closing',
      [ReadyState.CLOSED]: 'Disconnected',
      [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
    };
    setConnectionStatus(connectionStatusMap[readyState]);
  }, [readyState]);

  
  useEffect(() => {
    if (readyState === ReadyState.OPEN) {
      sendMessage(JSON.stringify({
        type: 'subscribe',
        subscriptions: ['timeline_updates', 'pending_tickets_updates', 'ticket_updates']
      }));
    }
  }, [readyState, sendMessage]);

 
  useEffect(() => {
    if (readyState === ReadyState.OPEN) {
      const pingInterval = setInterval(() => {
        sendMessage(JSON.stringify({ type: 'ping' }));
      }, 30000); 

      return () => clearInterval(pingInterval);
    }
  }, [readyState, sendMessage]);

  return {
    timeline,
    pendingTickets,
    connectionStatus,
    isConnected: readyState === ReadyState.OPEN,
    lastMessage,
    sendMessage: (message) => {
      if (readyState === ReadyState.OPEN) {
        sendMessage(JSON.stringify(message));
      }
    }
  };
};

export default useTicketWebSocket;
