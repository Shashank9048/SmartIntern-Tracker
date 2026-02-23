import { APIClient } from './api-client'

export interface Application {
  _id: string
  userId: string
  companyName: string
  position: string
  appliedDate: string
  status: 'applied' | 'interviewing' | 'rejected' | 'offer' | 'accepted'
  jobUrl?: string
  salary?: string
  matchScore?: number
  notes?: string
  createdAt: string
  updatedAt: string
}

export interface Resume {
  _id: string
  userId: string
  filename: string
  fileUrl: string
  uploadedAt: string
  isPrimary: boolean
  analysisScore?: number
}

export interface User {
  _id: string
  email: string
  name: string
  password: string
  createdAt: string
  updatedAt: string
}

export interface AutomationRule {
  _id: string
  userId: string
  name: string
  trigger: string
  action: string
  isEnabled: boolean
}

export class MongoDBService {
  // Applications
  static async getApplications(userId: string): Promise<Application[]> {
    try {
      const response = await APIClient.get<{ applications: Application[] }>(
        `/api/applications?userId=${userId}`
      )
      return response.applications
    } catch (error) {
      console.error('Error fetching applications:', error)
      throw error
    }
  }

  static async createApplication(data: Omit<Application, '_id' | 'createdAt' | 'updatedAt'>): Promise<Application> {
    try {
      const response = await APIClient.post<Application>('/api/applications', data)
      return response
    } catch (error) {
      console.error('Error creating application:', error)
      throw error
    }
  }

  static async updateApplication(id: string, data: Partial<Application>): Promise<Application> {
    try {
      const response = await APIClient.put<Application>(`/api/applications/${id}`, data)
      return response
    } catch (error) {
      console.error('Error updating application:', error)
      throw error
    }
  }

  static async deleteApplication(id: string): Promise<void> {
    try {
      await APIClient.delete(`/api/applications/${id}`)
    } catch (error) {
      console.error('Error deleting application:', error)
      throw error
    }
  }

  // Resumes
  static async getResumes(userId: string): Promise<Resume[]> {
    try {
      const response = await APIClient.get<{ resumes: Resume[] }>(
        `/api/resumes?userId=${userId}`
      )
      return response.resumes
    } catch (error) {
      console.error('Error fetching resumes:', error)
      throw error
    }
  }

  static async uploadResume(userId: string, file: File): Promise<Resume> {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('userId', userId)

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/resumes/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error('Failed to upload resume')
      }

      return response.json()
    } catch (error) {
      console.error('Error uploading resume:', error)
      throw error
    }
  }

  static async deleteResume(id: string): Promise<void> {
    try {
      await APIClient.delete(`/api/resumes/${id}`)
    } catch (error) {
      console.error('Error deleting resume:', error)
      throw error
    }
  }

  static async setPrimaryResume(id: string): Promise<Resume> {
    try {
      const response = await APIClient.put<Resume>(`/api/resumes/${id}/primary`, {})
      return response
    } catch (error) {
      console.error('Error setting primary resume:', error)
      throw error
    }
  }

  // Users
  static async registerUser(email: string, password: string, name: string): Promise<User> {
    try {
      const response = await APIClient.post<User>('/api/auth/register', {
        email,
        password,
        name,
      })
      return response
    } catch (error) {
      console.error('Error registering user:', error)
      throw error
    }
  }

  static async loginUser(email: string, password: string): Promise<{ user: User; token: string }> {
    try {
      const response = await APIClient.post<{ user: User; token: string }>(
        '/api/auth/login',
        { email, password }
      )
      return response
    } catch (error) {
      console.error('Error logging in:', error)
      throw error
    }
  }

  static async getUserProfile(userId: string): Promise<User> {
    try {
      const response = await APIClient.get<User>(`/api/users/${userId}`)
      return response
    } catch (error) {
      console.error('Error fetching user profile:', error)
      throw error
    }
  }

  static async updateUserProfile(userId: string, data: Partial<User>): Promise<User> {
    try {
      const response = await APIClient.put<User>(`/api/users/${userId}`, data)
      return response
    } catch (error) {
      console.error('Error updating user profile:', error)
      throw error
    }
  }

  // Automation
  static async getAutomationRules(userId: string): Promise<AutomationRule[]> {
    try {
      const response = await APIClient.get<{ rules: AutomationRule[] }>(
        `/api/automation?userId=${userId}`
      )
      return response.rules
    } catch (error) {
      console.error('Error fetching automation rules:', error)
      throw error
    }
  }

  static async createAutomationRule(data: Omit<AutomationRule, '_id'>): Promise<AutomationRule> {
    try {
      const response = await APIClient.post<AutomationRule>('/api/automation', data)
      return response
    } catch (error) {
      console.error('Error creating automation rule:', error)
      throw error
    }
  }

  static async updateAutomationRule(id: string, data: Partial<AutomationRule>): Promise<AutomationRule> {
    try {
      const response = await APIClient.put<AutomationRule>(`/api/automation/${id}`, data)
      return response
    } catch (error) {
      console.error('Error updating automation rule:', error)
      throw error
    }
  }

  static async deleteAutomationRule(id: string): Promise<void> {
    try {
      await APIClient.delete(`/api/automation/${id}`)
    } catch (error) {
      console.error('Error deleting automation rule:', error)
      throw error
    }
  }

  // Analytics
  static async getApplicationStats(userId: string): Promise<{
    total: number
    applied: number
    interviewing: number
    rejected: number
    offers: number
  }> {
    try {
      const response = await APIClient.get<{
        total: number
        applied: number
        interviewing: number
        rejected: number
        offers: number
      }>(`/api/analytics/stats?userId=${userId}`)
      return response
    } catch (error) {
      console.error('Error fetching stats:', error)
      throw error
    }
  }
}
