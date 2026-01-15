import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MainLayout } from './components/layout'
import { ChatContainer } from './components/chat'
import { useHealth } from './hooks'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
})

function AppContent() {
  // Initialize health check to set mock mode
  useHealth()

  return (
    <MainLayout>
      <ChatContainer />
    </MainLayout>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  )
}

export default App
