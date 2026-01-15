import type {
  ChatRequest,
  ChatResponse,
  ChatHistoryResponse,
  OrderListResponse,
  OrderSyncResponse,
  Order,
  RateRequest,
  RatesResponse,
  CreateShipmentRequest,
  Shipment,
  TrackingResponse,
  HealthResponse,
} from './types'

const API_BASE = ''

class ApiError extends Error {
  status: number
  code?: string

  constructor(response: Response, data?: { error?: string; code?: string }) {
    super(data?.error || `API Error: ${response.status}`)
    this.name = 'ApiError'
    this.status = response.status
    this.code = data?.code
  }
}

async function request<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!res.ok) {
    let data
    try {
      data = await res.json()
    } catch {
      // ignore parse error
    }
    throw new ApiError(res, data)
  }

  return res.json()
}

export const api = {
  // Health
  async getHealth(): Promise<HealthResponse> {
    return request('/api/health')
  },

  // Chat
  async sendMessage(req: ChatRequest): Promise<ChatResponse> {
    return request('/api/chat', {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  async getChatHistory(sessionId: string, limit = 50): Promise<ChatHistoryResponse> {
    return request(`/api/chat/history?session_id=${sessionId}&limit=${limit}`)
  },

  async resetChat(sessionId: string): Promise<{ status: string; session_id: string }> {
    return request(`/api/reset?session_id=${sessionId}`, {
      method: 'POST',
    })
  },

  // Orders
  async getOrders(params?: {
    limit?: number
    status?: string
    search?: string
  }): Promise<OrderListResponse> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.status) searchParams.set('status', params.status)
    if (params?.search) searchParams.set('search', params.search)
    const query = searchParams.toString()
    return request(`/api/orders${query ? `?${query}` : ''}`)
  },

  async getOrder(orderId: string): Promise<Order> {
    return request(`/api/orders/${orderId}`)
  },

  async syncOrders(status = 'unfulfilled', limit = 50): Promise<OrderSyncResponse> {
    return request(`/api/orders/sync?status=${status}&limit=${limit}`, {
      method: 'POST',
    })
  },

  async fulfillOrder(orderId: string): Promise<{ status: string; order_id: string; tracking_number?: string }> {
    return request(`/api/orders/${orderId}/fulfill`, {
      method: 'POST',
    })
  },

  // Rates
  async getRates(req: RateRequest): Promise<RatesResponse> {
    return request('/api/rates', {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  // Shipments
  async createShipment(req: CreateShipmentRequest): Promise<Shipment> {
    return request('/api/shipments', {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  async getShipment(shipmentId: string): Promise<Shipment> {
    return request(`/api/shipments/${shipmentId}`)
  },

  async getTracking(shipmentId: string): Promise<TrackingResponse> {
    return request(`/api/shipments/${shipmentId}/tracking`)
  },
}

export { ApiError }
