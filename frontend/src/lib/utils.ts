import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount)
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(date))
}

export function formatRelativeTime(date: string | Date): string {
  const now = new Date()
  const then = new Date(date)
  const diff = now.getTime() - then.getTime()

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days < 7) return `${days}d ago`
  return formatDate(date)
}

export function getDeliveryDate(days: number | null): string | null {
  if (days === null) return null
  const date = new Date()
  date.setDate(date.getDate() + days)
  return formatDate(date)
}

export function getSessionId(): string {
  const key = 'shippingAgentSessionId'
  let sessionId = localStorage.getItem(key)
  if (!sessionId) {
    sessionId = `session_${Math.random().toString(36).substring(2, 11)}_${Date.now()}`
    localStorage.setItem(key, sessionId)
  }
  return sessionId
}
