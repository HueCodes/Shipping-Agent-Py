import type { WSMessage } from './types'

type MessageHandler = (message: WSMessage) => void
type ConnectionHandler = (connected: boolean) => void

export class ChatWebSocket {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnects = 5
  private reconnectDelay = 1000
  private reconnectTimer: number | null = null

  constructor(
    private onMessage: MessageHandler,
    private onConnectionChange: ConnectionHandler
  ) {}

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/chat/stream`

    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('WebSocket connected')
        this.reconnectAttempts = 0
        this.onConnectionChange(true)
      }

      this.ws.onclose = (event) => {
        console.log('WebSocket disconnected', event.code, event.reason)
        this.onConnectionChange(false)
        this.scheduleReconnect()
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WSMessage
          this.onMessage(data)
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }
    } catch (err) {
      console.error('WebSocket connection failed:', err)
      this.onConnectionChange(false)
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
    }

    if (this.reconnectAttempts < this.maxReconnects) {
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts)
      console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`)

      this.reconnectTimer = window.setTimeout(() => {
        this.reconnectAttempts++
        this.connect()
      }, delay)
    }
  }

  send(message: string, sessionId: string): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      return false
    }

    this.ws.send(
      JSON.stringify({
        message,
        session_id: sessionId,
      })
    )
    return true
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.reconnectAttempts = this.maxReconnects // Prevent reconnection
    this.ws?.close()
    this.ws = null
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}
