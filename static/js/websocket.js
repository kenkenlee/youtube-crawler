// WebSocket connection management

class WebSocketManager {
    constructor() {
        this.connections = {};
    }

    connect(sessionId, onMessage) {
        if (this.connections[sessionId]) {
            console.log(`Already connected to session ${sessionId}`);
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/sessions/${sessionId}`;

        console.log(`Connecting to WebSocket: ${wsUrl}`);

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log(`WebSocket connected for session ${sessionId}`);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (onMessage) {
                    onMessage(data);
                }
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };

        ws.onerror = (error) => {
            console.error(`WebSocket error for session ${sessionId}:`, error);
        };

        ws.onclose = () => {
            console.log(`WebSocket closed for session ${sessionId}`);
            delete this.connections[sessionId];
        };

        this.connections[sessionId] = ws;
    }

    disconnect(sessionId) {
        if (this.connections[sessionId]) {
            this.connections[sessionId].close();
            delete this.connections[sessionId];
        }
    }

    disconnectAll() {
        Object.keys(this.connections).forEach(sessionId => {
            this.disconnect(sessionId);
        });
    }

    send(sessionId, message) {
        if (this.connections[sessionId] && this.connections[sessionId].readyState === WebSocket.OPEN) {
            this.connections[sessionId].send(JSON.stringify(message));
        }
    }
}

// Global WebSocket manager instance
const wsManager = new WebSocketManager();

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    wsManager.disconnectAll();
});
