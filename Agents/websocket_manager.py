import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_info: Dict[WebSocket, Dict] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.connection_info[websocket] = {
            "client_id": client_id or f"client_{len(self.active_connections)}",
            "connected_at": datetime.now().isoformat(),
            "subscriptions": set()
        }
        logger.info(f"WebSocket connected: {self.connection_info[websocket]['client_id']}")
        
        await self.send_personal_message({
            "type": "connection_established",
            "client_id": self.connection_info[websocket]["client_id"],
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            client_id = self.connection_info.get(websocket, {}).get("client_id", "unknown")
            self.active_connections.remove(websocket)
            if websocket in self.connection_info:
                del self.connection_info[websocket]
            logger.info(f"WebSocket disconnected: {client_id}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict, event_type: str = None):
        """Broadcast a message to all connected clients"""
        if not self.active_connections:
            return
            
        message_with_metadata = {
            **message,
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type or message.get("type", "broadcast")
        }
        
        connections_to_remove = []
        
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(json.dumps(message_with_metadata))
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                connections_to_remove.append(connection)
        
        for connection in connections_to_remove:
            self.disconnect(connection)
    
    async def broadcast_ticket_update(self, update_type: str, data: dict):
        """Broadcast ticket-related updates"""
        message = {
            "type": "ticket_update",
            "update_type": update_type,
            "data": data
        }
        await self.broadcast(message, "ticket_update")
    
    async def broadcast_timeline_update(self, timeline: list):
        """Broadcast timeline updates"""
        message = {
            "type": "timeline_update",
            "timeline": timeline
        }
        await self.broadcast(message, "timeline_update")
    
    async def broadcast_pending_tickets_update(self, pending_tickets: list):
        """Broadcast pending tickets updates"""
        message = {
            "type": "pending_tickets_update",
            "pending_tickets": pending_tickets
        }
        await self.broadcast(message, "pending_tickets_update")
    
    async def handle_client_message(self, websocket: WebSocket, message: dict):
        """Handle incoming messages from clients"""
        message_type = message.get("type")
        
        if message_type == "subscribe":
            subscriptions = message.get("subscriptions", [])
            if websocket in self.connection_info:
                self.connection_info[websocket]["subscriptions"].update(subscriptions)
                await self.send_personal_message({
                    "type": "subscription_confirmed",
                    "subscriptions": list(self.connection_info[websocket]["subscriptions"])
                }, websocket)
        
        elif message_type == "ping":
            await self.send_personal_message({
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            }, websocket)
        
        else:
            logger.warning(f"Unknown message type: {message_type}")
    
    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self.active_connections)
    
    def get_connection_info(self) -> list:
        """Get information about all active connections"""
        return [
            {
                "client_id": info["client_id"],
                "connected_at": info["connected_at"],
                "subscriptions": list(info["subscriptions"])
            }
            for info in self.connection_info.values()
        ]

websocket_manager = WebSocketManager()
