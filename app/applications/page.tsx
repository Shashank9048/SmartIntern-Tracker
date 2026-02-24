'use client'

import { AppLayout } from '@/components/app-layout'
import { APIClient } from '@/lib/api-client'
import { AddApplicationModal } from '@/components/applications/add-application-modal'
import { EditApplicationModal } from '@/components/applications/edit-application-modal'
import { ApplicationCard } from '@/components/applications/application-card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Search, LayoutGrid, List, Zap, RefreshCw } from 'lucide-react'
import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/context/auth-context'
import { useApplicationContext } from '@/context/application-context'
import { toast } from 'sonner'

import { Application } from '@/types'

// Removed mockApplications

export default function ApplicationsPage() {
  const { user } = useAuth()
  const { applications, loading, error, addApplication, updateApplication, deleteApplication, refetch } = useApplicationContext()
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [viewMode, setViewMode] = useState<'grid' | 'kanban'>('grid')
  const [editingApp, setEditingApp] = useState<Application | null>(null)
  const [scoring, setScoring] = useState(false)
  const autoScoredRef = useRef(false)

  // Auto-score pending apps once user + apps both load
  useEffect(() => {
    const pendingCount = applications.filter((a: Application) => a.ai_match_score == null).length
    if (
      !loading &&
      !autoScoredRef.current &&
      pendingCount > 0 &&
      (user as any)?.resume_text
    ) {
      autoScoredRef.current = true
      handleScoreAll(true) // silent auto-score
    }
  }, [applications, loading, user])

  const filteredApplications = applications.filter((app: Application) => {
    const company = app.company_name || '';
    const role = app.role || '';

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
    } catch {
    }
  }

  const handleFollowUp = async (app: Application) => {
    try {
      // Create a follow-up automation scheduled 7 days from now
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
    } catch (error) {
      toast.error('Failed to create follow-up reminder')
    }
  }

  const handleDeleteApplication = async (id: string) => {
    try {
      await deleteApplication(id)
      toast.success('Application deleted successfully')
    } catch {
    }
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
        await refetch?.() // refresh app list to show new scores
      }
    } catch (err: any) {
      if (!silent) toast.error(err?.message || 'Scoring failed', { id: 'score-all' })
    } finally {
      setScoring(false)
    }
  }

  const pendingAICount = applications.filter((a: Application) => a.ai_match_score == null).length
  const hasResume = !!(user as any)?.resume_text

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold mb-2">Applications</h1>
            <p className="text-muted-foreground">
              Manage all your internship applications
            </p>
          </div>
          <AddApplicationModal onAdd={handleAddApplication} />
        </div>

        {/* Score All Banner — shown when pending apps exist */}
        {pendingAICount > 0 && hasResume && (
          <div className="flex items-center justify-between gap-4 glass rounded-xl px-5 py-3 border border-primary/20 bg-primary/5">
            <div className="flex items-center gap-3">
              <Zap className="w-5 h-5 text-primary shrink-0" />
              <p className="text-sm">
                <span className="font-semibold text-white">{pendingAICount} application{pendingAICount > 1 ? 's' : ''}</span>
                <span className="text-muted-foreground"> {pendingAICount > 1 ? 'are' : 'is'} missing an AI match score.</span>
              </p>
            </div>
            <Button
              size="sm"
              onClick={() => handleScoreAll(false)}
              disabled={scoring}
              className="shrink-0 bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30"
            >
              {scoring
                ? <><RefreshCw className="w-3 h-3 mr-1.5 animate-spin" /> Scoring…</>
                : <><Zap className="w-3 h-3 mr-1.5" /> Score with AI</>}
            </Button>
          </div>
        )}

        {/* No-resume hint */}
        {pendingAICount > 0 && !hasResume && (
          <div className="flex items-center gap-3 glass rounded-xl px-5 py-3 border border-yellow-500/20 bg-yellow-500/5">
            <Zap className="w-5 h-5 text-yellow-400 shrink-0" />
            <p className="text-sm text-muted-foreground">
              <span className="text-yellow-400 font-medium">Upload your resume</span> on the Resume page to get AI match scores for your applications.
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
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <div key={n} className="glass rounded-xl p-6 h-[220px] animate-pulse flex flex-col">
                <div className="h-6 bg-white/10 rounded w-1/2 mb-2"></div>
                <div className="h-4 bg-white/10 rounded w-1/3 mb-6"></div>
                <div className="h-6 bg-white/10 rounded w-1/4 mb-4"></div>
                <div className="h-2 bg-white/10 rounded-full w-full mt-auto mb-6"></div>
                <div className="flex gap-2">
                  <div className="h-8 bg-white/10 rounded flex-1"></div>
                  <div className="h-8 bg-white/10 rounded flex-1"></div>
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
          <div className="flex gap-6 overflow-x-auto pb-4 custom-scrollbar">
            {['Applied', 'Interview', 'Selected', 'Rejected'].map((statusOption) => (
              <div key={statusOption} className="flex-1 min-w-[300px] bg-white/5 border border-white/10 rounded-xl p-4 flex flex-col gap-4">
                <div className="flex items-center justify-between pb-2 border-b border-white/10">
                  <h3 className="font-semibold text-sm">{statusOption}</h3>
                  <span className="text-xs bg-white/10 px-2 py-1 rounded-full text-muted-foreground">
                    {filteredApplications.filter(a => a.status === statusOption).length}
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

        {filteredApplications.length === 0 && (
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">
              No applications added yet. Start tracking your internships 🚀
            </p>
            <AddApplicationModal onAdd={handleAddApplication} />
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
