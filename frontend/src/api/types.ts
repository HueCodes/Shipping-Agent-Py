// Chat Types
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp?: string
}

export interface ChatRequest {
  message: string
  session_id: string
}

export interface ChatResponse {
  response: string
  session_id: string
}

export interface ChatHistoryResponse {
  session_id: string
  messages: ChatMessage[]
  total: number
}

// WebSocket Message Types
export type WSMessage =
  | { type: 'status'; message: string; status?: string }
  | { type: 'tool_start'; tool: string; message?: string }
  | { type: 'tool_complete'; tool: string; success?: boolean; message?: string }
  | { type: 'chunk'; content: string }
  | { type: 'complete'; content?: string; session_id?: string }
  | { type: 'error'; message: string; code?: string }

// Order Types
export interface OrderAddress {
  name?: string
  street1?: string
  street2?: string
  city?: string
  state?: string
  zip?: string
  country?: string
  phone?: string
}

export interface OrderLineItem {
  id?: string
  title?: string
  name?: string
  quantity: number
  price?: string | number
  sku?: string
  grams?: number
  variant_title?: string
}

export interface Order {
  id: string
  shopify_order_id: string
  order_number: string | null
  recipient_name: string | null
  shipping_address: OrderAddress | null
  line_items: OrderLineItem[] | null
  weight_oz: number | null
  status: 'unfulfilled' | 'fulfilled' | 'partial' | 'processing'
  created_at: string | null
}

export interface OrderListResponse {
  orders: Order[]
  total: number
}

export interface OrderSyncResponse {
  synced: number
  created: number
  updated: number
  errors: string[]
}

// Rate Types
export interface Rate {
  rate_id: string
  carrier: string
  service: string
  price: number
  delivery_days: number | null
}

export interface RateRequest {
  order_id?: string
  to_city?: string
  to_state?: string
  to_zip?: string
  weight_oz?: number
  length?: number
  width?: number
  height?: number
}

export interface RatesResponse {
  rates: Rate[]
}

// Shipment Types
export interface CreateShipmentRequest {
  rate_id: string
  to_name: string
  to_street: string
  to_city: string
  to_state: string
  to_zip: string
  weight_oz: number
  length?: number
  width?: number
  height?: number
  order_id?: string
}

export interface Shipment {
  id: string
  order_id: string | null
  tracking_number: string | null
  carrier: string
  service: string
  rate_amount: number | null
  label_url: string | null
  status: string
  estimated_delivery: string | null
  created_at: string | null
}

// Tracking Types
export interface TrackingEvent {
  status: string
  description: string | null
  location: { city?: string; state?: string; description?: string } | null
  occurred_at: string
}

export interface TrackingResponse {
  tracking_number: string
  carrier: string
  status: string
  estimated_delivery: string | null
  events: TrackingEvent[]
}

// Health Types
export interface HealthResponse {
  status: string
  mock_mode: boolean
  version?: string
}

// Customer Types
export interface CustomerResponse {
  id: string
  name: string
  shop_domain: string
  plan_tier: string
  labels_this_month: number
  labels_limit: number
  labels_remaining: number
}
