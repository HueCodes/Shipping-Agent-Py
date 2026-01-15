export interface CarrierInfo {
  name: string
  color: string
  bgColor: string
  textColor: string
}

export const carriers: Record<string, CarrierInfo> = {
  USPS: {
    name: 'USPS',
    color: '#004B87',
    bgColor: 'bg-blue-900/30',
    textColor: 'text-blue-300',
  },
  UPS: {
    name: 'UPS',
    color: '#351C15',
    bgColor: 'bg-amber-900/30',
    textColor: 'text-amber-300',
  },
  FedEx: {
    name: 'FedEx',
    color: '#4D148C',
    bgColor: 'bg-purple-900/30',
    textColor: 'text-purple-300',
  },
  DHL: {
    name: 'DHL',
    color: '#D40511',
    bgColor: 'bg-red-900/30',
    textColor: 'text-red-300',
  },
}

export function getCarrierInfo(carrier: string): CarrierInfo {
  const normalized = carrier.toUpperCase()
  if (normalized.includes('USPS')) return carriers.USPS
  if (normalized.includes('UPS')) return carriers.UPS
  if (normalized.includes('FEDEX')) return carriers.FedEx
  if (normalized.includes('DHL')) return carriers.DHL
  return {
    name: carrier,
    color: '#64748b',
    bgColor: 'bg-slate-700/30',
    textColor: 'text-slate-300',
  }
}

export function getServiceLevel(service: string): 'ground' | 'express' | 'overnight' {
  const lower = service.toLowerCase()
  if (lower.includes('overnight') || lower.includes('next day') || lower.includes('priority overnight')) {
    return 'overnight'
  }
  if (lower.includes('express') || lower.includes('2nd day') || lower.includes('2day') || lower.includes('priority')) {
    return 'express'
  }
  return 'ground'
}
