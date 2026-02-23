'use client'

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { APIClient } from '@/lib/api-client'
import { Application } from '@/types'
import { useAuth } from './auth-context'
import { toast } from 'sonner'

interface ApplicationStats {
    total: number
    interviews: number
    offers: number
    rejected: number
    chartData: any[]
}

interface ApplicationContextType {
    applications: Application[]
    stats: ApplicationStats
    loading: boolean
    error: Error | null
    addApplication: (data: any) => Promise<Application>
    updateApplication: (id: string, data: Partial<Application>) => Promise<Application>
    deleteApplication: (id: string) => Promise<void>
    refetch: () => Promise<void>
}

const ApplicationContext = createContext<ApplicationContextType | undefined>(undefined)

export function ApplicationProvider({ children }: { children: React.ReactNode }) {
    const { user, token } = useAuth()
    const [applications, setApplications] = useState<Application[]>([])
    const [stats, setStats] = useState<ApplicationStats>({ total: 0, interviews: 0, offers: 0, rejected: 0, chartData: [] })
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<Error | null>(null)

    const computeStats = useCallback((apps: Application[]) => {
        const total = apps.length
        const interviews = apps.filter(a => a.status === 'Interview').length
        const offers = apps.filter(a => a.status === 'Selected').length
        const rejected = apps.filter(a => a.status === 'Rejected').length

        // Simple monthly aggregation
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        const monthlyCounts: Record<string, number> = {}

        apps.forEach(app => {
            const date = new Date(app.applied_date)
            if (!isNaN(date.getTime())) {
                const month = monthNames[date.getMonth()]
                monthlyCounts[month] = (monthlyCounts[month] || 0) + 1
            }
        })

        const chartData = Object.keys(monthlyCounts).map(month => ({
            month,
            applications: monthlyCounts[month]
        }))

        setStats({ total, interviews, offers, rejected, chartData })
    }, [])

    const fetchApplications = useCallback(async () => {
        if (!user || !token) {
            setApplications([])
            setStats({ total: 0, interviews: 0, offers: 0, rejected: 0, chartData: [] })
            return
        }

        setLoading(true)
        setError(null)
        try {
            const data = await APIClient.get<Application[]>('/api/applications')
            setApplications(data)
            computeStats(data)
        } catch (err) {
            console.error(err)
            setError(err instanceof Error ? err : new Error('Failed to fetch applications'))
        } finally {
            setLoading(false)
        }
    }, [user, token, computeStats])

    useEffect(() => {
        fetchApplications()
    }, [fetchApplications])

    const addApplication = useCallback(async (data: Omit<Application, '_id' | 'user_id' | 'created_at' | 'updated_at'>) => {
        try {
            const newApp = await APIClient.post<Application>('/api/applications', data)
            setApplications(prev => {
                const next = [newApp, ...prev]
                computeStats(next)
                return next
            })
            return newApp
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to add application')
            setError(error)
            toast.error(error.message)
            throw error
        }
    }, [computeStats])

    const updateApplication = useCallback(async (id: string, data: Partial<Application>) => {
        try {
            const updated = await APIClient.patch<Application>(`/api/applications/${id}`, data)
            setApplications(prev => {
                const next = prev.map(app => (app._id === id ? updated : app))
                computeStats(next)
                return next
            })
            return updated
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to update application')
            setError(error)
            toast.error(error.message)
            throw error
        }
    }, [computeStats])

    const deleteApplication = useCallback(async (id: string) => {
        try {
            await APIClient.delete(`/api/applications/${id}`)
            setApplications(prev => {
                const next = prev.filter(app => app._id !== id)
                computeStats(next)
                return next
            })
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to delete application')
            setError(error)
            toast.error(error.message)
            throw error
        }
    }, [computeStats])

    return (
        <ApplicationContext.Provider
            value={{
                applications,
                stats,
                loading,
                error,
                addApplication,
                updateApplication,
                deleteApplication,
                refetch: fetchApplications
            }}
        >
            {children}
        </ApplicationContext.Provider>
    )
}

export function useApplicationContext() {
    const context = useContext(ApplicationContext)
    if (context === undefined) {
        throw new Error('useApplicationContext must be used within an ApplicationProvider')
    }
    return context
}
