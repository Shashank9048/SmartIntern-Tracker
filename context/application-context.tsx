'use client'

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { APIClient } from '@/lib/api-client'
import { Application, TrackedJobEntry, TrackedJobStatus } from '@/types'
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
    trackedJobs: TrackedJobEntry[]
    stats: ApplicationStats
    loading: boolean
    error: Error | null
    addApplication: (data: any) => Promise<Application>
    updateApplication: (id: string, data: Partial<Application>) => Promise<Application>
    deleteApplication: (id: string) => Promise<void>
    addTrackedJob: (jobId: string, status: TrackedJobStatus) => Promise<TrackedJobEntry>
    updateTrackedJobStatus: (id: string, status: TrackedJobStatus) => Promise<TrackedJobEntry>
    deleteTrackedJob: (id: string) => Promise<void>
    refetch: () => Promise<void>
}

const ApplicationContext = createContext<ApplicationContextType | undefined>(undefined)

export function ApplicationProvider({ children }: { children: React.ReactNode }) {
    const { user, token } = useAuth()
    const [applications, setApplications] = useState<Application[]>([])
    const [trackedJobs, setTrackedJobs] = useState<TrackedJobEntry[]>([])
    const [stats, setStats] = useState<ApplicationStats>({ total: 0, interviews: 0, offers: 0, rejected: 0, chartData: [] })
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<Error | null>(null)

    const computeStats = useCallback((apps: Application[], tJobs: TrackedJobEntry[]) => {
        const manualTotal = apps.length
        const trackedTotal = tJobs.length
        const total = manualTotal + trackedTotal

        const manualInterviews = apps.filter(a => a.status === 'Interview').length
        const trackedInterviews = tJobs.filter(t => t.status === 'interview' || t.status === 'oa').length
        const interviews = manualInterviews + trackedInterviews

        const manualOffers = apps.filter(a => a.status === 'Selected' || a.status === 'Offer').length
        const trackedOffers = tJobs.filter(t => t.status === 'offer').length
        const offers = manualOffers + trackedOffers

        const manualRejected = apps.filter(a => a.status === 'Rejected').length
        const trackedRejected = tJobs.filter(t => t.status === 'rejected').length
        const rejected = manualRejected + trackedRejected

        // Unified monthly aggregation
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        const monthlyCounts: Record<string, number> = {}

        apps.forEach(app => {
            const date = new Date(app.applied_date || app.created_at)
            if (!isNaN(date.getTime())) {
                const month = monthNames[date.getMonth()]
                monthlyCounts[month] = (monthlyCounts[month] || 0) + 1
            }
        })

        tJobs.forEach(tj => {
            const date = new Date(tj.created_at || tj.updated_at)
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

    const fetchAllData = useCallback(async () => {
        if (!user || !token) {
            setApplications([])
            setTrackedJobs([])
            setStats({ total: 0, interviews: 0, offers: 0, rejected: 0, chartData: [] })
            return
        }

        setLoading(true)
        setError(null)
        try {
            const [appsData, trackedData] = await Promise.all([
                APIClient.get<Application[]>('/api/applications').catch(err => {
                    console.warn('[Applications] Fetch apps error:', err)
                    return [] as Application[]
                }),
                APIClient.get<TrackedJobEntry[]>('/api/tracked-jobs').catch(err => {
                    console.warn('[Applications] Fetch tracked jobs error:', err)
                    return [] as TrackedJobEntry[]
                })
            ])

            setApplications(appsData)
            setTrackedJobs(trackedData)
            computeStats(appsData, trackedData)
        } catch (err) {
            const isNetworkErr =
                err instanceof Error &&
                (err.name === 'NetworkError' || err.message.startsWith('NetworkError'))
            if (isNetworkErr) {
                console.warn('[Applications] Backend unreachable — keeping cached data.')
            } else {
                console.error('[Applications] Fetch error:', err)
                setError(err instanceof Error ? err : new Error('Failed to fetch application data'))
            }
        } finally {
            setLoading(false)
        }
    }, [user, token, computeStats])

    const notifyChange = () => {
        if (typeof window !== 'undefined') {
            const channel = new BroadcastChannel('app_sync')
            channel.postMessage('data_changed')
            channel.close()
        }
    }

    useEffect(() => {
        fetchAllData()
        
        if (typeof window !== 'undefined') {
            const channel = new BroadcastChannel('app_sync')
            channel.onmessage = (e) => {
                if (e.data === 'data_changed') {
                    fetchAllData()
                }
            }
            return () => channel.close()
        }
    }, [fetchAllData])

    const addApplication = useCallback(async (data: Omit<Application, '_id' | 'user_id' | 'created_at' | 'updated_at'>) => {
        const tempId = 'temp-' + Date.now()
        const tempApp = {
            ...data,
            _id: tempId,
            user_id: 'temp',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
        } as Application

        setApplications(prev => {
            const next = [tempApp, ...prev]
            computeStats(next, trackedJobs)
            return next
        })
        notifyChange()

        try {
            const newApp = await APIClient.post<Application>('/api/applications', data)
            setApplications(prev => {
                // Replace the temporary application with the one from the server
                const next = prev.map(app => app._id === tempId ? newApp : app)
                computeStats(next, trackedJobs)
                return next
            })
            notifyChange()
            return newApp
        } catch (err) {
            // Revert on error
            setApplications(prev => {
                const next = prev.filter(app => app._id !== tempId)
                computeStats(next, trackedJobs)
                return next
            })
            notifyChange()
            const error = err instanceof Error ? err : new Error('Failed to add application')
            setError(error)
            toast.error(error.message)
            throw error
        }
    }, [computeStats, trackedJobs])

    const updateApplication = useCallback(async (id: string, data: Partial<Application>) => {
        try {
            const updated = await APIClient.patch<Application>(`/api/applications/${id}`, data)
            setApplications(prev => {
                const next = prev.map(app => (app._id === id ? updated : app))
                computeStats(next, trackedJobs)
                return next
            })
            notifyChange()
            return updated
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to update application')
            setError(error)
            toast.error(error.message)
            throw error
        }
    }, [computeStats, trackedJobs])

    const deleteApplication = useCallback(async (id: string) => {
        try {
            await APIClient.delete(`/api/applications/${id}`)
            await fetchAllData() // Refetch fully to sync deletion from TrackedJobs
            notifyChange()
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to delete application')
            setError(error)
            toast.error(error.message)
            throw error
        }
    }, [fetchAllData])

    const addTrackedJob = useCallback(async (jobId: string, status: TrackedJobStatus, matchScore?: number, jobData?: any) => {
        try {
            const payload: any = { job_id: jobId, status }
            if (matchScore !== undefined) payload.match_score = matchScore
            if (jobData !== undefined) payload.job_data = jobData
            
            const newTracked = await APIClient.post<TrackedJobEntry>('/api/tracked-jobs', payload)
            setTrackedJobs(prev => {
                const next = [newTracked, ...prev.filter(t => t.job_id !== jobId)]
                computeStats(applications, next)
                return next
            })
            notifyChange()
            return newTracked
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to track job')
            toast.error(error.message)
            throw error
        }
    }, [computeStats, applications])

    const updateTrackedJobStatus = useCallback(async (id: string, status: TrackedJobStatus) => {
        try {
            const updated = await APIClient.patch<TrackedJobEntry>(`/api/tracked-jobs/${id}`, { status })
            setTrackedJobs(prev => {
                const next = prev.map(t => (t._id === id ? updated : t))
                computeStats(applications, next)
                return next
            })
            notifyChange()
            return updated
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to update tracked job status')
            toast.error(error.message)
            throw error
        }
    }, [computeStats, applications])

    const deleteTrackedJob = useCallback(async (id: string) => {
        try {
            await APIClient.delete(`/api/tracked-jobs/${id}`)
            setTrackedJobs(prev => {
                const next = prev.filter(t => t._id !== id)
                computeStats(applications, next)
                return next
            })
            notifyChange()
        } catch (err) {
            const error = err instanceof Error ? err : new Error('Failed to delete tracked job')
            toast.error(error.message)
            throw error
        }
    }, [computeStats, applications])

    return (
        <ApplicationContext.Provider
            value={{
                applications,
                trackedJobs,
                stats,
                loading,
                error,
                addApplication,
                updateApplication,
                deleteApplication,
                addTrackedJob,
                updateTrackedJobStatus,
                deleteTrackedJob,
                refetch: fetchAllData
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
