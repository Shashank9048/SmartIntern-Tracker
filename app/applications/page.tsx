'use client'

import { AppLayout } from '@/components/app-layout'
import { APIClient } from '@/lib/api-client'
import { AddApplicationModal } from '@/components/applications/add-application-modal'
import { EditApplicationModal } from '@/components/applications/edit-application-modal'
import { ApplicationCard } from '@/components/applications/application-card'
import { JobCard } from '@/components/applications/job-card'
import { KanbanBoard } from '@/components/applications/kanban-board'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import {
  Search,
  LayoutGrid,
  List,
  Zap,
  RefreshCw,
  Sparkles,
  FolderOpen,
  ChevronRight,
} from 'lucide-react'
import { useEffect, useState, useRef, useCallback } from 'react'
import { useAuth } from '@/context/auth-context'
import { useApplicationContext } from '@/context/application-context'
import { toast } from 'sonner'
import Link from 'next/link'

import { Application, RecommendedJobEntry, MatchStatus, TrackedJobStatus, TrackedJobEntry } from '@/types'

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components for the Recommended feed states
// ─────────────────────────────────────────────────────────────────────────────

function ComputingState() {
  const [dots, setDots] = useState('_')

  useEffect(() => {
    const frames = ['_', '__', '___', '']
    let i = 0
    const id = setInterval(() => {
      i = (i + 1) % frames.length
      setDots(frames[i])
    }, 500)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="border border-dashed border-white/20 rounded-2xl py-16 px-8 flex flex-col items-center justify-center gap-4 bg-white/[0.02]">
      <div
        className="text-lg text-amber-400/80 font-mono select-none"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {'> computing your matches'}
        <span className="text-amber-400">{dots}</span>
      </div>
      <p className="text-sm text-muted-foreground text-center max-w-xs">
        We're scoring jobs against your resume in the background. This usually
        takes a few seconds.
      </p>
    </div>
  )
}

function NoResumeState() {
  const [blink, setBlink] = useState(true)

  useEffect(() => {
    const id = setInterval(() => setBlink((b) => !b), 600)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="border border-dashed border-white/20 rounded-2xl py-16 px-8 flex flex-col items-center justify-center gap-4 bg-white/[0.02]">
      <div
        className="text-lg text-muted-foreground font-mono select-none"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {'> no resume found'}
        <span
          className="inline-block w-[2px] h-[1.1em] bg-primary align-[-2px] ml-0.5 transition-opacity"
          style={{ opacity: blink ? 1 : 0 }}
        />
      </div>
      <p className="text-sm text-muted-foreground text-center max-w-xs">
        Upload your resume to start getting personalised job recommendations.
      </p>
      <Link href="/resume">
        <Button
          size="sm"
          className="bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30 gap-1.5"
        >
          <ChevronRight className="w-3.5 h-3.5" />
          Go to Resume page
        </Button>
      </Link>
    </div>
  )
}

function EmptyMatchesState() {
  const [blink, setBlink] = useState(true)

  useEffect(() => {
    const id = setInterval(() => setBlink((b) => !b), 600)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="border border-dashed border-white/20 rounded-2xl py-16 px-8 flex flex-col items-center justify-center gap-4 bg-white/[0.02]">
      <div
        className="text-lg text-muted-foreground font-mono select-none"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {'> no matches found'}
        <span
          className="inline-block w-[2px] h-[1.1em] bg-muted-foreground align-[-2px] ml-0.5 transition-opacity"
          style={{ opacity: blink ? 1 : 0 }}
        />
      </div>
      <p className="text-sm text-muted-foreground text-center max-w-xs">
        Try lowering the score filter, or update your resume with more skills.
      </p>
      <Link href="/resume">
        <Button
          size="sm"
          variant="outline"
          className="border-white/10 gap-1.5 hover:bg-white/5"
        >
          <ChevronRight className="w-3.5 h-3.5" />
          Update Resume
        </Button>
      </Link>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

type Tab = 'recommended' | 'applications'

export default function ApplicationsPage() {
  const { user } = useAuth()
  const {
    applications,
    loading,
    addApplication,
    updateApplication,
    deleteApplication,
    refetch,
  } = useApplicationContext()

  // ── Tab state ──────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<Tab>('recommended')

  // ── My Applications state ─────────────────────────────────────────────────
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [viewMode, setViewMode] = useState<'grid' | 'kanban'>('grid')
  const [editingApp, setEditingApp] = useState<Application | null>(null)
  const [scoring, setScoring] = useState(false)
  const autoScoredRef = useRef(false)

  // ── Recommended feed state ─────────────────────────────────────────────────
  const [matchStatus, setMatchStatus] = useState<MatchStatus>('computing')
  const [recommendedJobs, setRecommendedJobs] = useState<RecommendedJobEntry[]>([])
  const [feedLoading, setFeedLoading] = useState(true)
  const [triggerFired, setTriggerFired] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Client-side score filter (0 = show all)
  const [minScoreFilter, setMinScoreFilter] = useState(0)
  // Track which job_ids have been actioned (applied/saved)
  const [trackedJobIds, setTrackedJobIds] = useState<Set<string>>(new Set())

  // ── Job Tracker (feed-sourced kanban) state ────────────────────────────
  const [trackedJobs, setTrackedJobs] = useState<TrackedJobEntry[]>([])
  const [trackerLoading, setTrackerLoading] = useState(false)
  const trackerFetchedRef = useRef(false)

  const fetchTrackedJobs = useCallback(async () => {
    setTrackerLoading(true)
    try {
      const data = await APIClient.get<TrackedJobEntry[]>('/api/tracked-jobs')
      setTrackedJobs(data)
      // Pre-populate the actioned set so JobCards in the feed show 'Tracked'
      setTrackedJobIds(new Set(data.map((t) => t.job_id)))
    } catch {
      // Silently fail
    } finally {
      setTrackerLoading(false)
    }
  }, [])

  const handleKanbanStatusChange = async (id: string, newStatus: TrackedJobStatus) => {
    try {
      const updated = await APIClient.patch<TrackedJobEntry>(`/api/tracked-jobs/${id}`, { status: newStatus })
      setTrackedJobs((prev) => prev.map((t) => (t._id === id ? updated : t)))
      const colLabels: Record<TrackedJobStatus, string> = {
        wishlist: 'Wishlist', applied: 'Applied', oa: 'OA',
        interview: 'Interview', offer: 'Offer', rejected: 'Rejected'
      }
      toast.success(`✓ Moved to ${colLabels[newStatus]}`, { duration: 2000 })
    } catch (e: any) {
      toast.error(e?.message || 'Failed to update status')
      throw e // Let KanbanBoard revert optimistic update
    }
  }

  const handleKanbanDelete = async (id: string) => {
    try {
      await APIClient.delete(`/api/tracked-jobs/${id}`)
      setTrackedJobs((prev) => prev.filter((t) => t._id !== id))
      toast.success('✓ Removed from tracker', { duration: 2000 })
    } catch (e: any) {
      toast.error(e?.message || 'Failed to remove')
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  const fetchRecommended = useCallback(async () => {
    try {
      // No min_score param — backend defaults to 0 (all jobs), we filter client-side
      const data = await APIClient.get<RecommendedJobEntry[]>('/api/jobs/recommended')
      setRecommendedJobs(data)
    } catch {
      // Silently fail — keep showing existing data
    }
  }, [])

  const triggerAndPoll = useCallback(async () => {
    if (triggerFired) return
    setTriggerFired(true)
    try {
      await APIClient.post('/api/jobs/match', {})
    } catch {
      // Non-fatal — status poll will catch the result
    }
  }, [triggerFired])

  const checkStatus = useCallback(async () => {
    try {
      const res = await APIClient.get<{
        status: MatchStatus
        match_count: number
      }>('/api/jobs/match/status')

      setMatchStatus(res.status)

      if (res.status === 'computing' && !triggerFired) {
        // Kick off the batch match if not already triggered
        triggerAndPoll()
        return
      }

      if (res.status === 'ready') {
        // Stop polling, load results
        if (pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
        await fetchRecommended()
        setFeedLoading(false)
        return
      }

      if (res.status === 'no_resume') {
        if (pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
        setFeedLoading(false)
      }
    } catch {
      setFeedLoading(false)
    }
  }, [fetchRecommended, triggerAndPoll, triggerFired])

  // Start status polling on mount
  useEffect(() => {
    checkStatus() // immediate first check
    pollRef.current = setInterval(checkStatus, 3000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [checkStatus])

  // Fetch tracked jobs when My Applications tab is first opened
  useEffect(() => {
    if (activeTab === 'applications' && !trackerFetchedRef.current) {
      trackerFetchedRef.current = true
      fetchTrackedJobs()
    }
  }, [activeTab, fetchTrackedJobs])

  // Auto-score pending application cards once user + apps load
  useEffect(() => {
    const pendingCount = applications.filter(
      (a: Application) => a.ai_match_score == null
    ).length
    if (
      !loading &&
      !autoScoredRef.current &&
      pendingCount > 0 &&
      (user as any)?.resume_text
    ) {
      autoScoredRef.current = true
      handleScoreAll(true)
    }
  }, [applications, loading, user])

  // ── Application handlers ───────────────────────────────────────────────────

  const filteredApplications = applications.filter((app: Application) => {
    const company = app.company_name || ''
    const role = app.role || ''
    const matchesSearch =
      company.toLowerCase().includes(searchTerm.toLowerCase()) ||
      role.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus =
      statusFilter === 'all' || app.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const handleAddApplication = async (data: any) => {
    try {
      await addApplication(data)
      toast.success('Application added successfully')
    } catch {
      // toast is handled in context
    }
  }

  const handleUpdateApplication = async (id: string, data: any) => {
    try {
      await updateApplication(id, data)
      toast.success('Application updated successfully')
      setEditingApp(null)
    } catch {}
  }

  const handleFollowUp = async (app: Application) => {
    try {
      const scheduledAt = new Date()
      scheduledAt.setDate(scheduledAt.getDate() + 7)
      await APIClient.post('/api/automations', {
        application_id: app._id,
        type: 'followup',
        scheduled_at: scheduledAt.toISOString(),
        email_enabled: true,
        ai_prep_enabled: false,
      })
      toast.success(`Follow-up reminder set for ${app.company_name}!`)
    } catch {
      toast.error('Failed to create follow-up reminder')
    }
  }

  const handleDeleteApplication = async (id: string) => {
    try {
      await deleteApplication(id)
      toast.success('Application deleted successfully')
    } catch {}
  }

  const handleScoreAll = async (silent = false) => {
    if (scoring) return
    setScoring(true)
    if (!silent) toast.loading('Scoring applications with AI…', { id: 'score-all' })
    try {
      const result: any = await APIClient.post('/api/applications/score-all', {})
      if (!silent) {
        toast.success(`Scored ${result.scored} application(s) with AI!`, { id: 'score-all' })
      }
      if (result.scored > 0) {
        await refetch?.()
      }
    } catch (err: any) {
      if (!silent) toast.error(err?.message || 'Scoring failed', { id: 'score-all' })
    } finally {
      setScoring(false)
    }
  }

  const pendingAICount = applications.filter(
    (a: Application) => a.ai_match_score == null
  ).length
  const hasResume = !!(user as any)?.resume_text

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold mb-2">Applications</h1>
            <p className="text-muted-foreground">
              Discover recommended roles and manage your applications
            </p>
          </div>
          {activeTab === 'applications' && (
            <AddApplicationModal onAdd={handleAddApplication} />
          )}
        </div>

        {/* ── Tab switcher ──────────────────────────────────────────────── */}
        <div className="flex gap-1 p-1 glass rounded-xl w-fit border border-white/10">
          <button
            onClick={() => setActiveTab('recommended')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
              activeTab === 'recommended'
                ? 'bg-amber-500/20 text-amber-400 border border-amber-400/20 shadow-sm shadow-amber-400/10'
                : 'text-muted-foreground hover:text-white hover:bg-white/5'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            Recommended
          </button>
          <button
            onClick={() => setActiveTab('applications')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
              activeTab === 'applications'
                ? 'bg-primary/20 text-primary border border-primary/20 shadow-sm shadow-primary/10'
                : 'text-muted-foreground hover:text-white hover:bg-white/5'
            }`}
          >
            <FolderOpen className="w-4 h-4" />
            My Applications
            {applications.length > 0 && (
              <span className="text-xs bg-white/10 px-1.5 py-0.5 rounded-full">
                {applications.length}
              </span>
            )}
          </button>
        </div>

        {/* ══════════════════════════════════════════════════════════════════ */}
        {/* TAB: RECOMMENDED                                                  */}
        {/* ══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'recommended' && (
          <div className="space-y-4">
            {/* Section header */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  Recommended for you
                </h2>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {matchStatus === 'ready' && recommendedJobs.length > 0
                    ? `${recommendedJobs.filter(j => j.match_score >= minScoreFilter).length} match${recommendedJobs.filter(j => j.match_score >= minScoreFilter).length !== 1 ? 'es' : ''} shown · filter by score below`
                    : 'Jobs scored against your resume · all scores shown'}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {/* Score filter dropdown */}
                {matchStatus === 'ready' && recommendedJobs.length > 0 && (
                  <Select
                    value={String(minScoreFilter)}
                    onValueChange={(v) => setMinScoreFilter(Number(v))}
                  >
                    <SelectTrigger className="w-36 glass border-white/10 rounded-lg text-xs h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-card border-white/10">
                      <SelectItem value="0">All scores</SelectItem>
                      <SelectItem value="50">50%+ match</SelectItem>
                      <SelectItem value="70">70%+ match</SelectItem>
                      <SelectItem value="85">85%+ match</SelectItem>
                    </SelectContent>
                  </Select>
                )}
                {/* Refresh button */}
                {matchStatus === 'ready' && recommendedJobs.length > 0 && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-white/10 hover:bg-white/5 gap-1.5 text-xs h-8"
                    onClick={async () => {
                      setTriggerFired(false)
                      setFeedLoading(true)
                      setMatchStatus('computing')
                      await APIClient.post('/api/jobs/match', {})
                      pollRef.current = setInterval(checkStatus, 3000)
                    }}
                  >
                    <RefreshCw className="w-3 h-3" />
                    Refresh
                  </Button>
                )}
              </div>
            </div>

            {/* Feed states */}
            {feedLoading || matchStatus === 'computing' ? (
              <ComputingState />
            ) : matchStatus === 'no_resume' ? (
              <NoResumeState />
            ) : recommendedJobs.filter(j => j.match_score >= minScoreFilter).length === 0 ? (
              <EmptyMatchesState />
            ) : (
              /* Populated: horizontal scroll strip */
              <div className="relative">
                {/* Fade edge indicator */}
                <div className="absolute right-0 top-0 bottom-0 w-16 bg-gradient-to-l from-background to-transparent z-10 pointer-events-none rounded-r-2xl" />
                <div
                  className="flex gap-4 overflow-x-auto pb-4 pr-8"
                  style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.1) transparent' }}
                >
                  {Array.from(new Map(recommendedJobs.map(j => [j.job_id, j])).values())
                    .filter(j => j.match_score >= minScoreFilter)
                    .map((entry, idx) => (
                      <JobCard
                        key={`${entry.job_id}-${idx}`}
                        entry={entry}
                        isTracked={trackedJobIds.has(entry.job_id)}
                        onApply={async (jobId) => {
                          try {
                            await APIClient.post('/api/tracked-jobs', { job_id: jobId, status: 'applied' })
                            setTrackedJobIds(prev => new Set([...prev, jobId]))
                            toast.success('✓ Tracked as Applied', { duration: 2500 })
                          } catch (e: any) {
                            console.error('[ApplicationsPage] Failed to track application:', e)
                            toast.error(e?.message || 'Failed to track application')
                            throw e
                          }
                        }}
                        onSave={async (jobId) => {
                          try {
                            await APIClient.post('/api/tracked-jobs', { job_id: jobId, status: 'wishlist' })
                            setTrackedJobIds(prev => new Set([...prev, jobId]))
                            toast.success('✓ Saved to Wishlist', { duration: 2500 })
                          } catch (e: any) {
                            toast.error(e?.message || 'Failed to save job')
                          }
                        }}
                      />
                    ))}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {recommendedJobs.filter(j => j.match_score >= minScoreFilter).length} match{recommendedJobs.filter(j => j.match_score >= minScoreFilter).length !== 1 ? 'es' : ''} · scroll to see more →
                </p>
              </div>
            )}
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════ */}
        {/* TAB: MY APPLICATIONS                                              */}
        {/* Phase 6: Kanban board will be added inside this tab panel         */}
        {/* ══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'applications' && (
          <div className="space-y-6">
            {/* Score All Banner */}
            {pendingAICount > 0 && hasResume && (
              <div className="flex items-center justify-between gap-4 glass rounded-xl px-5 py-3 border border-primary/20 bg-primary/5">
                <div className="flex items-center gap-3">
                  <Zap className="w-5 h-5 text-primary shrink-0" />
                  <p className="text-sm">
                    <span className="font-semibold text-white">
                      {pendingAICount} application{pendingAICount > 1 ? 's' : ''}
                    </span>
                    <span className="text-muted-foreground">
                      {' '}{pendingAICount > 1 ? 'are' : 'is'} missing an AI match score.
                    </span>
                  </p>
                </div>
                <Button
                  size="sm"
                  onClick={() => handleScoreAll(false)}
                  disabled={scoring}
                  className="shrink-0 bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30"
                >
                  {scoring ? (
                    <><RefreshCw className="w-3 h-3 mr-1.5 animate-spin" /> Scoring…</>
                  ) : (
                    <><Zap className="w-3 h-3 mr-1.5" /> Score with AI</>
                  )}
                </Button>
              </div>
            )}

            {/* No-resume hint */}
            {pendingAICount > 0 && !hasResume && (
              <div className="flex items-center gap-3 glass rounded-xl px-5 py-3 border border-yellow-500/20 bg-yellow-500/5">
                <Zap className="w-5 h-5 text-yellow-400 shrink-0" />
                <p className="text-sm text-muted-foreground">
                  <span className="text-yellow-400 font-medium">Upload your resume</span>{' '}
                  on the Resume page to get AI match scores for your applications.
                </p>
              </div>
            )}

            {/* Filters */}
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search applications..."
                  className="glass pl-10 border-white/10 rounded-lg"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full md:w-48 glass border-white/10 rounded-lg">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-card border-white/10">
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="Applied">Applied</SelectItem>
                  <SelectItem value="Interview">Interview</SelectItem>
                  <SelectItem value="Selected">Selected</SelectItem>
                  <SelectItem value="Rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>

              <div className="flex gap-2">
                <Button
                  variant={viewMode === 'grid' ? 'default' : 'outline'}
                  size="icon"
                  onClick={() => setViewMode('grid')}
                  className={viewMode === 'grid' ? 'bg-primary text-white' : 'border-white/10'}
                >
                  <LayoutGrid className="w-4 h-4" />
                </Button>
                <Button
                  variant={viewMode === 'kanban' ? 'default' : 'outline'}
                  size="icon"
                  onClick={() => setViewMode('kanban')}
                  className={viewMode === 'kanban' ? 'bg-primary text-white' : 'border-white/10'}
                >
                  <List className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Applications Grid / Kanban */}
            {/* Phase 6 note: Kanban board component will be inserted in this block */}
            {loading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <div key={n} className="glass rounded-xl p-6 h-[220px] animate-pulse flex flex-col">
                    <div className="h-6 bg-white/10 rounded w-1/2 mb-2" />
                    <div className="h-4 bg-white/10 rounded w-1/3 mb-6" />
                    <div className="h-6 bg-white/10 rounded w-1/4 mb-4" />
                    <div className="h-2 bg-white/10 rounded-full w-full mt-auto mb-6" />
                    <div className="flex gap-2">
                      <div className="h-8 bg-white/10 rounded flex-1" />
                      <div className="h-8 bg-white/10 rounded flex-1" />
                    </div>
                  </div>
                ))}
              </div>
            ) : viewMode === 'grid' ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredApplications.map((app: Application) => (
                  <ApplicationCard
                    key={app._id}
                    id={app._id}
                    company_name={app.company_name}
                    role={app.role}
                    status={app.status}
                    applied_date={app.applied_date}
                    interview_date={app.interview_date}
                    matchScore={app.ai_match_score ?? undefined}
                    onDelete={() => handleDeleteApplication(app._id)}
                    onEdit={() => setEditingApp(app)}
                    onFollowUp={() => handleFollowUp(app)}
                  />
                ))}
              </div>
            ) : (
              /* Real KanbanBoard for manual applications */
              <div className="flex gap-6 overflow-x-auto pb-4" style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.1) transparent' }}>
                {['Applied', 'Interview', 'Selected', 'Rejected'].map((statusOption) => (
                  <div
                    key={statusOption}
                    className="flex-1 min-w-[300px] bg-white/5 border border-white/10 rounded-xl p-4 flex flex-col gap-4"
                  >
                    <div className="flex items-center justify-between pb-2 border-b border-white/10">
                      <h3 className="font-semibold text-sm">{statusOption}</h3>
                      <span className="text-xs bg-white/10 px-2 py-1 rounded-full text-muted-foreground">
                        {filteredApplications.filter((a) => a.status === statusOption).length}
                      </span>
                    </div>
                    <div className="flex flex-col gap-4">
                      {filteredApplications
                        .filter((app: Application) => app.status === statusOption)
                        .map((app: Application) => (
                          <ApplicationCard
                            key={app._id}
                            id={app._id}
                            company_name={app.company_name}
                            role={app.role}
                            status={app.status}
                            applied_date={app.applied_date}
                            interview_date={app.interview_date}
                            matchScore={app.ai_match_score ?? undefined}
                            onDelete={() => handleDeleteApplication(app._id)}
                            onEdit={() => setEditingApp(app)}
                            onFollowUp={() => handleFollowUp(app)}
                          />
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {filteredApplications.length === 0 && !loading && (
              <div className="text-center py-12">
                <p className="text-muted-foreground mb-4">
                  No applications added yet. Start tracking your internships 🚀
                </p>
                <AddApplicationModal onAdd={handleAddApplication} />
              </div>
            )}

            {/* ════════════════════════════════════════════════════ */}
            {/* JOB TRACKER — feed-sourced kanban (Phase 6B)             */}
            {/* ════════════════════════════════════════════════════ */}
            <div className="pt-2">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h2 className="text-base font-semibold flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                    Job Tracker
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Jobs saved/applied from the Recommended feed · drag to update status
                  </p>
                </div>
                <button
                  onClick={fetchTrackedJobs}
                  className="text-xs text-muted-foreground hover:text-white flex items-center gap-1 transition-colors"
                  disabled={trackerLoading}
                >
                  <RefreshCw className={`w-3 h-3 ${trackerLoading ? 'animate-spin' : ''}`} />
                  {trackerLoading ? 'Loading…' : 'Refresh'}
                </button>
              </div>

              {trackerLoading ? (
                <div className="flex gap-3 overflow-x-auto pb-4">
                  {[1,2,3,4,5,6].map((n) => (
                    <div key={n} className="min-w-[230px] h-[120px] glass rounded-xl animate-pulse" />
                  ))}
                </div>
              ) : trackedJobs.length === 0 ? (
                <div className="border border-dashed border-white/10 rounded-xl py-8 flex flex-col items-center justify-center gap-2 bg-white/[0.01]">
                  <p
                    className="text-sm text-muted-foreground font-mono"
                    style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  >
                    {'> no jobs tracked yet'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Click Save or Apply on a Recommended card to add jobs here.
                  </p>
                </div>
              ) : (
                <KanbanBoard
                  items={trackedJobs}
                  onStatusChange={handleKanbanStatusChange}
                  onDelete={handleKanbanDelete}
                />
              )}
            </div>
          </div>
        )}
      </div>

      <EditApplicationModal
        application={editingApp}
        open={!!editingApp}
        onOpenChange={(open) => !open && setEditingApp(null)}
        onUpdate={handleUpdateApplication}
      />
    </AppLayout>
  )
}
