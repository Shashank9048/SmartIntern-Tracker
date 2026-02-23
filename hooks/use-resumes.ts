'use client'

import { useCallback, useEffect, useState } from 'react'
import { Resume, MongoDBService } from '@/lib/mongodb-service'

export function useResumes(userId?: string) {
  const [resumes, setResumes] = useState<Resume[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchResumes = useCallback(async () => {
    if (!userId) return

    setLoading(true)
    setError(null)
    try {
      const data = await MongoDBService.getResumes(userId)
      setResumes(data)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to fetch resumes'))
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    fetchResumes()
  }, [fetchResumes])

  const uploadResume = useCallback(
    async (file: File) => {
      if (!userId) return

      try {
        const newResume = await MongoDBService.uploadResume(userId, file)
        setResumes((prev) => [...prev, newResume])
        return newResume
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to upload resume')
        setError(error)
        throw error
      }
    },
    [userId]
  )

  const deleteResume = useCallback(async (id: string) => {
    try {
      await MongoDBService.deleteResume(id)
      setResumes((prev) => prev.filter((r) => r._id !== id))
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to delete resume')
      setError(error)
      throw error
    }
  }, [])

  const setPrimaryResume = useCallback(async (id: string) => {
    try {
      const updated = await MongoDBService.setPrimaryResume(id)
      setResumes((prev) =>
        prev.map((r) => ({
          ...r,
          isPrimary: r._id === id,
        }))
      )
      return updated
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to set primary resume')
      setError(error)
      throw error
    }
  }, [])

  return {
    resumes,
    loading,
    error,
    uploadResume,
    deleteResume,
    setPrimaryResume,
    refetch: fetchResumes,
  }
}
