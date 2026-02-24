'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'
import { APIClient } from '@/lib/api-client'
import { getUserProfile, UserProfile } from '../src/services/api'

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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)


  const loadUserFromBackend = async (authToken: string) => {
    try {
      localStorage.setItem('access_token', authToken);
      const profile = await getUserProfile();
      setUser(profile as AuthUser);
      setToken(authToken);
      localStorage.setItem('auth_user', JSON.stringify(profile));
    } catch (error) {
      console.error('Failed to load user profile:', error);
      // Only logout on explicit auth failure, not network issues
      if (error instanceof Error && error.message.includes('401')) {
        logout();
      }
    }
  }

  const refreshUser = async () => {
    const currentToken = token || localStorage.getItem('access_token');
    if (currentToken) {
      // Set the token in state immediately to avoid race conditions
      if (!token) setToken(currentToken);
      await loadUserFromBackend(currentToken);
    }
  }

  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = localStorage.getItem('access_token');
      if (storedToken) {
        setToken(storedToken);
        // Optimistic load
        const storedUser = localStorage.getItem('auth_user');
        if (storedUser) {
          try {
            const parsed = JSON.parse(storedUser);
            setUser(parsed);
          } catch (e) {
            console.error('Failed to parse cached user', e);
          }
        }
        // Verify and get fresh data
        await loadUserFromBackend(storedToken);
      }
      setLoading(false)
    }

    initializeAuth();
  }, [])

  const login = async (email: string, password: string) => {
    // Left empty as login is currently handled directly in the login page via services/api.ts
    // This context structure remains to not break existing usage
  }

  const register = async (email: string, password: string, name: string) => {
    // Left empty for same reason
  }

  const loginWithGoogle = async (token: string) => {
    // Left empty for same reason
  }

  const logout = () => {
    setUser(null)
    setToken(null)
    APIClient.setToken(null)
    localStorage.removeItem('auth_user')
    localStorage.removeItem('access_token')
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
