'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'
import { APIClient, getApiBaseUrl } from '@/lib/api-client'
import { getUserProfile, loginUser, UserProfile } from '../src/services/api'

// Extended user model including the API profile fields
export interface AuthUser extends UserProfile {
  _id?: string
  profile_picture?: string
}

interface AuthContextType {
  user: AuthUser | null
  token: string | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  loginWithGoogle: (token: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const API_BASE = typeof window !== 'undefined' ? getApiBaseUrl() : (process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000')

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const loadUserFromBackend = React.useCallback(async (authToken: string) => {
    try {
      localStorage.setItem('access_token', authToken)
      const profile = await getUserProfile()
      setUser(profile as AuthUser)
      setToken(authToken)
      localStorage.setItem('auth_user', JSON.stringify(profile))
    } catch (error) {
      const isNetworkError =
        error instanceof TypeError ||
        (error instanceof Error &&
          (error.message === 'Failed to fetch' ||
           error.message.includes('NetworkError') ||
           error.message.includes('unreachable') ||
           error.message.includes('net::ERR')))

      if (isNetworkError) {
        // Backend unreachable — stay logged in using cached user from localStorage
        console.warn('[Auth] Backend unreachable — using cached session. Will retry on next action.')
        return
      }

      if (error instanceof Error && (error.message.includes('401') || error.message.includes('403'))) {
        // Token is invalid or expired — force logout
        console.warn('[Auth] Token rejected by server — logging out.')
        logout()
      } else {
        console.warn('[Auth] Profile fetch failed (non-critical):', error instanceof Error ? error.message : error)
      }
    }
  }, [])

  const refreshUser = React.useCallback(async () => {
    const currentToken = localStorage.getItem('access_token')
    if (currentToken) {
      await loadUserFromBackend(currentToken)
    }
  }, [loadUserFromBackend])

  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = localStorage.getItem('access_token')
      if (storedToken) {
        setToken(storedToken)
        // Optimistic load from cache first for instant UI
        const storedUser = localStorage.getItem('auth_user')
        if (storedUser) {
          try {
            const parsed = JSON.parse(storedUser)
            setUser(parsed)
          } catch (e) {
            console.error('Failed to parse cached user', e)
          }
        }
        // Verify token and get fresh data from server
        await loadUserFromBackend(storedToken)
      }
      setLoading(false)
    }

    initializeAuth()
  }, [])

  /**
   * Full login implementation: calls backend, stores token, loads profile.
   * Previously this was an empty stub — now it's the canonical login path.
   */
  const login = async (email: string, password: string) => {
    const data = await loginUser(email, password)
    if (!data.access_token) throw new Error('No access token received')

    // Persist token in both localStorage and cookie (for Next.js middleware)
    localStorage.setItem('access_token', data.access_token)
    document.cookie = `access_token=${data.access_token}; path=/; max-age=604800; SameSite=Lax`

    await loadUserFromBackend(data.access_token)
  }

  const register = async (_email: string, _password: string, _name: string) => {
    // Signup is handled directly on the signup page (it has extra fields like branch/skills).
    // After signup the page calls refreshUser() to sync state — this stub stays for type compatibility.
  }

  const loginWithGoogle = async (_token: string) => {
    // Google OAuth stub — kept for type compatibility
  }

  const logout = () => {
    // Best-effort server-side ack (fire-and-forget — don't await, don't block UI)
    const currentToken = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
    if (currentToken) {
      fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${currentToken}` },
      }).catch(() => {}) // silently ignore network errors on logout
    }

    // Clear client-side state
    setUser(null)
    setToken(null)
    APIClient.setToken(null)
    localStorage.removeItem('auth_user')
    localStorage.removeItem('access_token')
    // Clear cookie too
    document.cookie = 'access_token=; path=/; max-age=0; SameSite=Lax'
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        loginWithGoogle,
        logout,
        isAuthenticated: !!user && !!token,
        refreshUser
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
