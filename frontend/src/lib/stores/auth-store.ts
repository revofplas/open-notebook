import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { getApiUrl } from '@/lib/config'

interface UserInfo {
  uid: string
  user_id: string
  emp_no: string
  emp_nm: string
  role: string
}

interface AuthState {
  isAuthenticated: boolean
  token: string | null
  user: UserInfo | null
  isLoading: boolean
  error: string | null
  lastAuthCheck: number | null
  isCheckingAuth: boolean
  hasHydrated: boolean
  authRequired: boolean | null
  setHasHydrated: (state: boolean) => void
  checkAuthRequired: () => Promise<boolean>
  login: (userId: string, password: string) => Promise<boolean>
  logout: () => void
  checkAuth: () => Promise<boolean>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      isAuthenticated: false,
      token: null,
      user: null,
      isLoading: false,
      error: null,
      lastAuthCheck: null,
      isCheckingAuth: false,
      hasHydrated: false,
      authRequired: null,

      setHasHydrated: (state: boolean) => {
        set({ hasHydrated: state })
      },

      checkAuthRequired: async () => {
        try {
          const apiUrl = await getApiUrl()
          const response = await fetch(`${apiUrl}/api/auth/status`, {
            cache: 'no-store',
          })

          if (!response.ok) {
            throw new Error(`Auth status check failed: ${response.status}`)
          }

          const data = await response.json()
          const required = data.auth_enabled || false
          set({ authRequired: required })

          // If auth is not required, mark as authenticated
          if (!required) {
            set({ isAuthenticated: true, token: 'not-required' })
          }

          return required
        } catch (error) {
          console.error('Failed to check auth status:', error)

          if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
            set({
              error: 'Unable to connect to server. Please check if the API is running.',
              authRequired: null
            })
          } else {
            set({ authRequired: true })
          }

          throw error
        }
      },

      login: async (userId: string, password: string) => {
        set({ isLoading: true, error: null })
        try {
          const apiUrl = await getApiUrl()

          const response = await fetch(`${apiUrl}/api/auth/login`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ user_id: userId, password }),
          })

          if (response.ok) {
            const data = await response.json()
            set({
              isAuthenticated: true,
              token: data.access_token,
              user: {
                uid: data.user.uid,
                user_id: data.user.user_id,
                emp_no: data.user.emp_no,
                emp_nm: data.user.emp_nm,
                role: data.user.role,
              },
              isLoading: false,
              lastAuthCheck: Date.now(),
              error: null,
            })
            return true
          } else {
            let errorMessage = '로그인에 실패했습니다'
            try {
              const errData = await response.json()
              errorMessage = errData.detail || errorMessage
            } catch {
              // ignore JSON parse error
            }
            if (response.status === 401) {
              errorMessage = '사용자 ID 또는 비밀번호가 올바르지 않습니다.'
            } else if (response.status === 403) {
              errorMessage = '접근이 거부되었습니다. 자격 증명을 확인하세요.'
            } else if (response.status >= 500) {
              errorMessage = '서버 오류입니다. 나중에 다시 시도하세요.'
            }

            set({
              error: errorMessage,
              isLoading: false,
              isAuthenticated: false,
              token: null,
              user: null,
            })
            return false
          }
        } catch (error) {
          console.error('Network error during auth:', error)
          let errorMessage = '로그인에 실패했습니다'

          if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
            errorMessage = '서버에 연결할 수 없습니다. API가 실행 중인지 확인하세요.'
          } else if (error instanceof Error) {
            errorMessage = `네트워크 오류: ${error.message}`
          }

          set({
            error: errorMessage,
            isLoading: false,
            isAuthenticated: false,
            token: null,
            user: null,
          })
          return false
        }
      },

      logout: () => {
        const { token } = get()
        // Fire-and-forget audit log
        if (token && token !== 'not-required') {
          getApiUrl().then(apiUrl => {
            fetch(`${apiUrl}/api/auth/logout`, {
              method: 'POST',
              headers: { 'Authorization': `Bearer ${token}` },
            }).catch(() => { /* ignore */ })
          }).catch(() => { /* ignore */ })
        }
        set({
          isAuthenticated: false,
          token: null,
          user: null,
          error: null,
        })
      },

      checkAuth: async () => {
        const state = get()
        const { token, lastAuthCheck, isCheckingAuth, isAuthenticated } = state

        if (isCheckingAuth) {
          return isAuthenticated
        }

        if (!token) {
          return false
        }

        // Skip check for 30 seconds if recently authenticated
        const now = Date.now()
        if (isAuthenticated && lastAuthCheck && (now - lastAuthCheck) < 30000) {
          return true
        }

        set({ isCheckingAuth: true })

        try {
          const apiUrl = await getApiUrl()

          const response = await fetch(`${apiUrl}/api/auth/me`, {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          })

          if (response.ok) {
            const userData = await response.json()
            set({
              isAuthenticated: true,
              user: {
                uid: userData.uid,
                user_id: userData.user_id,
                emp_no: userData.emp_no,
                emp_nm: userData.emp_nm,
                role: userData.role,
              },
              lastAuthCheck: now,
              isCheckingAuth: false,
            })
            return true
          } else {
            set({
              isAuthenticated: false,
              token: null,
              user: null,
              lastAuthCheck: null,
              isCheckingAuth: false,
            })
            return false
          }
        } catch (error) {
          console.error('checkAuth error:', error)
          set({
            isAuthenticated: false,
            token: null,
            user: null,
            lastAuthCheck: null,
            isCheckingAuth: false,
          })
          return false
        }
      }
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        isAuthenticated: state.isAuthenticated,
        user: state.user,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true)
      }
    }
  )
)
