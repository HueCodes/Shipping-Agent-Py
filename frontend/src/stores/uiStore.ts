import { create } from 'zustand'

interface UIState {
  sidebarOpen: boolean
  selectedOrderId: string | null
  mockMode: boolean

  // Modal states
  labelPreviewOpen: boolean
  labelPreviewUrl: string | null
  trackingModalOpen: boolean
  trackingShipmentId: string | null

  // Actions
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  selectOrder: (orderId: string | null) => void
  setMockMode: (mock: boolean) => void
  openLabelPreview: (url: string) => void
  closeLabelPreview: () => void
  openTrackingModal: (shipmentId: string) => void
  closeTrackingModal: () => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: false,
  selectedOrderId: null,
  mockMode: true,
  labelPreviewOpen: false,
  labelPreviewUrl: null,
  trackingModalOpen: false,
  trackingShipmentId: null,

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  selectOrder: (orderId) => set({ selectedOrderId: orderId }),

  setMockMode: (mock) => set({ mockMode: mock }),

  openLabelPreview: (url) =>
    set({ labelPreviewOpen: true, labelPreviewUrl: url }),

  closeLabelPreview: () =>
    set({ labelPreviewOpen: false, labelPreviewUrl: null }),

  openTrackingModal: (shipmentId) =>
    set({ trackingModalOpen: true, trackingShipmentId: shipmentId }),

  closeTrackingModal: () =>
    set({ trackingModalOpen: false, trackingShipmentId: null }),
}))
