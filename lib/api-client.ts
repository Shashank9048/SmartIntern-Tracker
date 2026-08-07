const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000'
).replace(/\/$/, '') // strip trailing slash to prevent double-slash URLs

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean>
}

export class APIClient {
  private static baseURL = API_BASE_URL

  static setToken(token: string | null) {
    if (token) {
      localStorage.setItem('access_token', token)
    } else {
      localStorage.removeItem('access_token')
    }
  }

  static getToken(): string | null {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('access_token')
  }

  static async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { params, ...fetchOptions } = options

    let url = `${this.baseURL}${endpoint}`

    if (params) {
      const searchParams = new URLSearchParams()
      Object.entries(params).forEach(([key, value]) => {
        searchParams.append(key, String(value))
      })
      url += `?${searchParams.toString()}`
    }

    const token = this.getToken()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(fetchOptions.headers as Record<string, string>),
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers,
      })

      if (!response.ok) {
        if (response.status === 401) {
          this.setToken(null)
          if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
            window.location.href = '/login?reason=session_expired'
          }
          throw new Error('Your session has expired. Please log in again.')
        }

        try {
          const error = await response.json()

          if (response.status === 422 && Array.isArray(error.detail)) {
            const validationErrors = error.detail.map((err: any) => {
              const field = err.loc[err.loc.length - 1]
              return `${field}: ${err.msg}`
            }).join(', ')
            throw new Error(`Validation Error: ${validationErrors}`)
          }

          throw new Error(error.message || error.error || `API Error: ${response.status}`)
        } catch (e) {
          if (e instanceof Error && e.message !== `API Error: ${response.status}`) {
            throw e
          }
          throw new Error(`API Error: ${response.status} ${response.statusText}`)
        }
      }

      return await response.json()
    } catch (error) {
      // Convert raw TypeError: "Failed to fetch" (network unreachable) into a
      // recognisable NetworkError so callers can silently handle it.
      if (error instanceof TypeError && error.message === 'Failed to fetch') {
        const networkErr = new Error(`NetworkError: Cannot reach ${this.baseURL}. Is the backend running?`)
        networkErr.name = 'NetworkError'
        throw networkErr
      }
      if (error instanceof Error) {
        throw error
      }
      throw new Error('Network error. Please check your connection and try again.')
    }
  }

  static async get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'GET',
    })
  }

  static async post<T>(
    endpoint: string,
    data?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  static async patch<T>(
    endpoint: string,
    data?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  static async put<T>(
    endpoint: string,
    data?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  static async delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'DELETE',
    })
  }
}
