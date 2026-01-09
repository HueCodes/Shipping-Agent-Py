/**
 * Shipping Agent - Frontend Application
 */

class ShippingAgentApp {
    constructor() {
        this.sessionId = this.getOrCreateSessionId();
        this.ws = null;
        this.wsReconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.isStreaming = false;
        this.currentStreamingMessage = null;
        this.orders = [];
        this.selectedOrder = null;
        this.sidebarOpen = false;

        this.elements = {
            chatContainer: document.getElementById('chat-container'),
            messageInput: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
            modeBadge: document.getElementById('mode-badge'),
            connectionBadge: document.getElementById('connection-badge'),
            sidebar: document.getElementById('sidebar'),
            sidebarContent: document.getElementById('sidebar-content'),
            sidebarOverlay: document.getElementById('sidebar-overlay'),
        };

        this.init();
    }

    getOrCreateSessionId() {
        let sessionId = localStorage.getItem('shippingAgentSessionId');
        if (!sessionId) {
            sessionId = 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
            localStorage.setItem('shippingAgentSessionId', sessionId);
        }
        return sessionId;
    }

    async init() {
        await this.checkHealth();
        await this.loadChatHistory();
        this.connectWebSocket();
        this.loadOrders();
        this.setupEventListeners();
        this.elements.messageInput?.focus();
    }

    setupEventListeners() {
        // Send message on Enter
        this.elements.messageInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Mobile sidebar overlay click
        this.elements.sidebarOverlay?.addEventListener('click', () => {
            this.toggleSidebar(false);
        });

        // Window resize - close sidebar on mobile
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768 && this.sidebarOpen) {
                this.toggleSidebar(false);
            }
        });
    }

    // WebSocket Connection
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/chat/stream`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.wsReconnectAttempts = 0;
                this.updateConnectionStatus(true);
            };

            this.ws.onclose = (e) => {
                console.log('WebSocket disconnected', e.code, e.reason);
                this.updateConnectionStatus(false);
                this.scheduleReconnect();
            };

            this.ws.onerror = (e) => {
                console.error('WebSocket error:', e);
            };

            this.ws.onmessage = (e) => {
                this.handleWebSocketMessage(JSON.parse(e.data));
            };
        } catch (e) {
            console.error('WebSocket connection failed:', e);
            this.updateConnectionStatus(false);
        }
    }

    scheduleReconnect() {
        if (this.wsReconnectAttempts < this.maxReconnectAttempts) {
            this.wsReconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.wsReconnectAttempts - 1);
            console.log(`Reconnecting in ${delay}ms (attempt ${this.wsReconnectAttempts})`);
            setTimeout(() => this.connectWebSocket(), delay);
        }
    }

    updateConnectionStatus(connected) {
        const badge = this.elements.connectionBadge;
        if (badge) {
            badge.classList.toggle('connected', connected);
            badge.classList.toggle('disconnected', !connected);
            const text = badge.querySelector('span:last-child');
            if (text) text.textContent = connected ? 'Live' : 'Offline';
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'status':
                this.showStatus(data.message);
                break;

            case 'tool_start':
                this.showToolStatus(data.tool, 'start');
                break;

            case 'tool_complete':
                this.showToolStatus(data.tool, 'complete', data.success);
                break;

            case 'chunk':
                this.appendStreamingChunk(data.content);
                break;

            case 'complete':
                this.finalizeStreamingMessage(data.content);
                break;

            case 'error':
                this.hideStatus();
                this.addMessage(data.message || 'An error occurred', 'error');
                this.isStreaming = false;
                this.enableInput();
                break;
        }
    }

    // Chat Operations
    async sendMessage() {
        const message = this.elements.messageInput?.value.trim();
        if (!message || this.isStreaming) return;

        // Add user message
        this.addMessage(message, 'user');
        this.elements.messageInput.value = '';
        this.disableInput();

        // Try WebSocket first
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.isStreaming = true;
            this.showTyping();
            this.ws.send(JSON.stringify({
                message: message,
                session_id: this.sessionId
            }));
        } else {
            // Fallback to REST API
            await this.sendMessageREST(message);
        }
    }

    async sendMessageREST(message) {
        this.showTyping();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, session_id: this.sessionId })
            });

            this.hideTyping();

            if (!res.ok) {
                const error = await res.json();
                this.addMessage(`Error: ${error.detail || 'Something went wrong'}`, 'error');
                return;
            }

            const data = await res.json();
            this.addMessage(data.response, 'agent');
        } catch (e) {
            this.hideTyping();
            this.addMessage(`Error: ${e.message}`, 'error');
        } finally {
            this.enableInput();
        }
    }

    async resetChat() {
        try {
            await fetch(`/api/reset?session_id=${this.sessionId}`, { method: 'POST' });
            this.elements.chatContainer.innerHTML = '';
            this.addMessage('Conversation cleared. How can I help you?', 'system');
        } catch (e) {
            console.error('Reset failed:', e);
        }
    }

    async loadChatHistory() {
        try {
            const res = await fetch(`/api/chat/history?session_id=${this.sessionId}&limit=50`);
            if (!res.ok) return;

            const data = await res.json();
            if (data.messages && data.messages.length > 0) {
                // Clear welcome message if we have history
                this.elements.chatContainer.innerHTML = '';

                for (const msg of data.messages) {
                    const type = msg.role === 'user' ? 'user' : 'agent';
                    this.addMessage(msg.content, type, false);
                }
                this.scrollToBottom();
            }
        } catch (e) {
            console.error('Failed to load chat history:', e);
        }
    }

    // UI Updates
    addMessage(content, type, animate = true) {
        const div = document.createElement('div');
        div.className = `message ${type}`;
        if (!animate) div.style.animation = 'none';

        if (type === 'agent') {
            div.innerHTML = this.renderAgentMessage(content);
        } else {
            div.textContent = content;
        }

        this.elements.chatContainer?.appendChild(div);
        this.scrollToBottom();
        return div;
    }

    renderAgentMessage(content) {
        // Check for structured content
        if (content.includes('RATE_CARDS:')) {
            return this.renderRateCards(content);
        }
        if (content.includes('TRACKING:')) {
            return this.renderTracking(content);
        }
        if (content.includes('ADDRESS:')) {
            return this.renderAddress(content);
        }

        // Standard markdown-ish parsing
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    renderRateCards(content) {
        // Parse rate cards from structured format
        // For now, just render as formatted text
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    }

    renderTracking(content) {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    }

    renderAddress(content) {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    }

    showTyping() {
        this.hideTyping();
        const div = document.createElement('div');
        div.className = 'typing-indicator';
        div.id = 'typing';
        div.innerHTML = '<span></span><span></span><span></span>';
        this.elements.chatContainer?.appendChild(div);
        this.scrollToBottom();
    }

    hideTyping() {
        document.getElementById('typing')?.remove();
    }

    showStatus(message) {
        this.hideStatus();
        const div = document.createElement('div');
        div.className = 'status-message';
        div.id = 'status';
        div.innerHTML = `<div class="spinner"></div><span>${this.escapeHtml(message)}</span>`;
        this.elements.chatContainer?.appendChild(div);
        this.scrollToBottom();
    }

    hideStatus() {
        document.getElementById('status')?.remove();
    }

    showToolStatus(tool, status, success = true) {
        const toolNames = {
            'get_rates': 'Fetching shipping rates',
            'create_shipment': 'Creating shipping label',
            'track_shipment': 'Getting tracking info',
            'validate_address': 'Validating address',
            'get_orders': 'Loading orders',
        };

        const displayName = toolNames[tool] || tool;

        if (status === 'start') {
            this.showStatus(`${displayName}...`);
        } else {
            this.hideStatus();
        }
    }

    appendStreamingChunk(content) {
        this.hideTyping();
        this.hideStatus();

        if (!this.currentStreamingMessage) {
            this.currentStreamingMessage = this.addMessage('', 'agent');
            this.currentStreamingMessage.dataset.streaming = 'true';
        }

        // Append with typewriter effect
        const currentContent = this.currentStreamingMessage.innerHTML;
        this.currentStreamingMessage.innerHTML = this.renderAgentMessage(
            this.stripHtml(currentContent) + content
        );
        this.scrollToBottom();
    }

    finalizeStreamingMessage(fullContent) {
        this.hideTyping();
        this.hideStatus();

        if (this.currentStreamingMessage) {
            this.currentStreamingMessage.innerHTML = this.renderAgentMessage(fullContent);
            delete this.currentStreamingMessage.dataset.streaming;
        } else {
            this.addMessage(fullContent, 'agent');
        }

        this.currentStreamingMessage = null;
        this.isStreaming = false;
        this.enableInput();
        this.scrollToBottom();
    }

    disableInput() {
        if (this.elements.sendBtn) this.elements.sendBtn.disabled = true;
        if (this.elements.messageInput) this.elements.messageInput.disabled = true;
    }

    enableInput() {
        if (this.elements.sendBtn) this.elements.sendBtn.disabled = false;
        if (this.elements.messageInput) {
            this.elements.messageInput.disabled = false;
            this.elements.messageInput.focus();
        }
    }

    scrollToBottom() {
        if (this.elements.chatContainer) {
            this.elements.chatContainer.scrollTop = this.elements.chatContainer.scrollHeight;
        }
    }

    // Orders Sidebar
    async loadOrders() {
        try {
            const res = await fetch('/api/orders');
            if (!res.ok) return;

            const data = await res.json();
            this.orders = data.orders || [];
            this.renderOrders();
        } catch (e) {
            console.error('Failed to load orders:', e);
        }
    }

    renderOrders() {
        if (!this.elements.sidebarContent) return;

        if (this.orders.length === 0) {
            this.elements.sidebarContent.innerHTML = `
                <div class="empty-orders">
                    <p style="color: var(--text-dim); text-align: center; padding: 2rem;">
                        No unfulfilled orders
                    </p>
                </div>
            `;
            return;
        }

        this.elements.sidebarContent.innerHTML = this.orders.map(order => `
            <div class="order-card ${this.selectedOrder?.id === order.id ? 'selected' : ''}"
                 data-order-id="${order.id}"
                 onclick="app.selectOrder('${order.id}')">
                <div class="order-header">
                    <span class="order-number">${this.escapeHtml(order.order_number)}</span>
                    <span class="order-status ${order.status}">${order.status}</span>
                </div>
                <div class="order-recipient">${this.escapeHtml(order.recipient_name)}</div>
                <div class="order-items">${this.formatOrderItems(order.line_items)}</div>
            </div>
        `).join('');
    }

    formatOrderItems(items) {
        if (!items || items.length === 0) return 'No items';
        const total = items.reduce((sum, item) => sum + (item.quantity || 1), 0);
        return `${total} item${total !== 1 ? 's' : ''}`;
    }

    selectOrder(orderId) {
        this.selectedOrder = this.orders.find(o => o.id === orderId) || null;
        this.renderOrders();

        if (this.selectedOrder) {
            // Auto-fill a shipping query for this order
            const address = this.selectedOrder.shipping_address || {};
            const suggestion = `Get shipping rates for order ${this.selectedOrder.order_number}`;
            this.elements.messageInput.value = suggestion;
            this.elements.messageInput.focus();

            // Close sidebar on mobile
            if (window.innerWidth <= 768) {
                this.toggleSidebar(false);
            }
        }
    }

    toggleSidebar(open = null) {
        this.sidebarOpen = open !== null ? open : !this.sidebarOpen;
        this.elements.sidebar?.classList.toggle('open', this.sidebarOpen);
        this.elements.sidebarOverlay?.classList.toggle('visible', this.sidebarOpen);
    }

    // Health Check
    async checkHealth() {
        try {
            const res = await fetch('/api/health');
            const data = await res.json();

            if (this.elements.modeBadge) {
                if (data.mock_mode) {
                    this.elements.modeBadge.textContent = 'MOCK';
                    this.elements.modeBadge.classList.remove('live');
                } else {
                    this.elements.modeBadge.textContent = 'LIVE';
                    this.elements.modeBadge.classList.add('live');
                }
            }
        } catch (e) {
            console.error('Health check failed:', e);
        }
    }

    // Utility functions
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    stripHtml(html) {
        const div = document.createElement('div');
        div.innerHTML = html;
        return div.textContent || '';
    }

    useSuggestion(text) {
        if (this.elements.messageInput) {
            this.elements.messageInput.value = text;
            this.elements.messageInput.focus();
        }
    }
}

// Initialize app
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new ShippingAgentApp();
});

// Global functions for onclick handlers
function sendMessage() {
    app?.sendMessage();
}

function resetChat() {
    app?.resetChat();
}

function useSuggestion(text) {
    app?.useSuggestion(text);
}

function toggleSidebar() {
    app?.toggleSidebar();
}
