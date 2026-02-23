'use client'

import { useCallback, useEffect, useState } from 'react'
import { APIClient } from '@/lib/api-client'
import { Application } from '@/types'

export function useApplications(userId?: string) {
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchApplications = useCallback(async () => {
    if (!userId) return

    setLoading(true)
    setError(null)
    try {
      const data = await APIClient.get<Application[]>('/applications')
      setApplications(data)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch applications'))
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    fetchApplications()
  }, [fetchApplications])

  const addApplication = useCallback(
    async (data: Omit<Application, '_id' | 'createdAt' | 'updatedAt'>) => {
      try {
        const newApp = await APIClient.post<Application>('/applications', data)
        setApplications((prev) => [...prev, newApp])
        return newApp
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to add application')
        setError(error)
        throw error
      }
    },
    []
  )

  const updateApplication = useCallback(async (id: string, data: Partial<Application>) => {
    try {
      const updated = await APIClient.patch<Application>(`/applications/${id}`, data)
      setApplications((prev) => prev.map((app) => (app._id === id ? updated : app)))
      return updated
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to update application')
      setError(error)
      throw error
    }
  }, [])

  const deleteApplication = useCallback(async (id: string) => {
    try {
      await APIClient.delete(`/applications/${id}`)
      setApplications((prev) => prev.filter((app) => app._id !== id))
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to delete application')
      setError(error)
      throw error
    }
  }, [])

  return {
    applications,
    loading,
    error,
    addApplication,
    updateApplication,
    deleteApplication,
    refetch: fetchApplications,
  }
}
