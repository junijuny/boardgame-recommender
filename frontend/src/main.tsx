import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App'

// TanStack Query: 서버 데이터를 불러오고 기억(캐시)해 두는 도구
// 같은 데이터를 다시 열면 기억해 둔 값을 바로 보여 준다.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,    // 5분 동안은 새로 불러오지 않음 (게임 데이터는 자주 바뀌지 않음)
      refetchOnWindowFocus: false, // 다른 탭에 다녀와도 다시 불러오지 않음
      retry: 1,                    // 실패하면 한 번만 다시 시도
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
