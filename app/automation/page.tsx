'use client'

import { AppLayout } from '@/components/app-layout'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import {
  Bell, Calendar, Clock, CheckCircle2, AlertTriangle,
  Zap, Plus, Trash2, ToggleLeft, ToggleRight, Loader2,
  BriefcaseIcon, Bot, Mail, RefreshCw, X
} from 'lucide-react'
import { useEffect, useState, useCallback } from 'react'
import { APIClient } from '@/lib/api-client'
import { toast } from 'sonner'

// ─── Types ────────────────────────────────────────────────────────────────────

interface AutomationStats {
  total_active: number
  upcoming_reminders: number
  interviews_this_week: number
  overdue_count: number
}

interface AutomationItem {
  _id: string
  application_id: string
  company: string
  role: string
  type: 'followup' | 'interview' | 'status'
  scheduled_at: string
  email_enabled: boolean
  ai_prep_enabled: boolean
  status: 'active' | 'paused' | 'completed'
  created_at: string
}

interface Application {
  _id: string
  company_name: string
  role: string
  status: string
}

const TYPE_LABELS: Record<string, string> = {
  followup: 'Follow-up Reminder',
  interview: 'Interview Reminder',
  status: 'Status Change Notification',
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  followup: <RefreshCw className="w-3.5 h-3.5" />,
  interview: <Calendar className="w-3.5 h-3.5" />,
  status: <Bell className="w-3.5 h-3.5" />,
}

// ─── Status Badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status, scheduledAt }: { status: string; scheduledAt: string }) {
  const now = new Date()
  const scheduled = new Date(scheduledAt.endsWith('Z') ? scheduledAt : scheduledAt + 'Z')

  if (status === 'completed') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
        <CheckCircle2 className="w-3 h-3" /> Completed
      </span>
    )
  }
  if (status === 'paused') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-yellow-400 border border-yellow-900/50">
        <Clock className="w-3 h-3" /> Paused
      </span>
    )
  }
  if (scheduled <= now) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-950/60 text-red-400 border border-red-900/50">
        <AlertTriangle className="w-3 h-3" /> Overdue
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-900/50">
      <Zap className="w-3 h-3" /> Active
    </span>
  )
}

// ─── Delete Confirmation Modal ────────────────────────────────────────────────

function DeleteModal({
  open,
  onClose,
  onConfirm,
  company,
  type,
  loading,
}: {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  company: string
  type: string
  loading: boolean
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative glass rounded-2xl p-6 w-full max-w-sm mx-4 shadow-2xl border border-white/10">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-muted-foreground hover:text-white transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-red-950/60 border border-red-900/50 flex items-center justify-center">
            <Trash2 className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h3 className="font-semibold text-white">Delete Automation</h3>
            <p className="text-xs text-muted-foreground">This action cannot be undone</p>
          </div>
        </div>
        <p className="text-sm text-muted-foreground mb-6">
          Are you sure you want to delete the{' '}
          <span className="text-white font-medium">{TYPE_LABELS[type] || type}</span>{' '}
          for <span className="text-white font-medium">{company}</span>?
        </p>
        <div className="flex gap-3">
          <Button variant="outline" className="flex-1" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            className="flex-1 bg-red-600 hover:bg-red-700 text-white border-0"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
            Delete
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AutomationPage() {
  const [stats, setStats] = useState<AutomationStats | null>(null)
  const [automations, setAutomations] = useState<AutomationItem[]>([])
  const [applications, setApplications] = useState<Application[]>([])
  const [loadingStats, setLoadingStats] = useState(true)
  const [loadingList, setLoadingList] = useState(true)
  const [saving, setSaving] = useState(false)
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [deleteModal, setDeleteModal] = useState<{ open: boolean; item: AutomationItem | null }>({
    open: false,
    item: null,
  })
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // Form state
  const [form, setForm] = useState({
    application_id: '',
    type: 'followup' as 'followup' | 'interview' | 'status',
    scheduled_at: '',
    email_enabled: true,
    ai_prep_enabled: true,
  })

  // ── Fetch helpers ────────────────────────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    try {
      const data = await APIClient.get<AutomationStats>('/api/automations/stats')
      setStats(data)
    } catch (e) {
      console.error('Stats error:', e)
    } finally {
      setLoadingStats(false)
    }
  }, [])

  const fetchAutomations = useCallback(async () => {
    try {
      const data = await APIClient.get<AutomationItem[]>('/api/automations')
      // Beanie (ODM) may return `id` or `_id` depending on serialization — normalize here
      const normalized = data.map((item: any) => ({
        ...item,
        _id: item._id || item.id || crypto.randomUUID(),
      }))
      setAutomations(normalized)
    } catch (e) {
      console.warn('Automations fetch error:', e)
    } finally {
      setLoadingList(false)
    }
  }, [])

  const fetchApplications = useCallback(async () => {
    try {
      const data = await APIClient.get<Application[]>('/api/applications')
      // Normalize `id` vs `_id` from Beanie serialization
      const normalized = data.map((app: any) => ({
        ...app,
        _id: app._id || app.id || '',
      }))
      setApplications(normalized)
    } catch (e) {
      console.warn('Applications fetch error:', e)
    }
  }, [])

  // ── Initial load + 30-second polling ────────────────────────────────────────

  useEffect(() => {
    fetchStats()
    fetchAutomations()
    fetchApplications()

    const interval = setInterval(() => {
      fetchStats()
      fetchAutomations()
    }, 30000)
    return () => clearInterval(interval)
  }, [fetchStats, fetchAutomations, fetchApplications])

  // ── Create automation ────────────────────────────────────────────────────────

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.application_id) {
      toast.error('Please select an application')
      return
    }
    if (!form.scheduled_at) {
      toast.error('Please select a date & time')
      return
    }
    setSaving(true)
    try {
      const payload = {
        ...form,
        scheduled_at: new Date(form.scheduled_at).toISOString(),
      }
      await APIClient.post('/api/automations', payload)
      toast.success('Automation created!')
      setForm({ application_id: '', type: 'followup', scheduled_at: '', email_enabled: true, ai_prep_enabled: true })
      fetchStats()
      fetchAutomations()
    } catch (err: any) {
      toast.error(err?.message || 'Failed to create automation')
    } finally {
      setSaving(false)
    }
  }

  // ── Toggle active/paused ─────────────────────────────────────────────────────

  const handleToggle = async (item: AutomationItem) => {
    if (item.status === 'completed') return
    setTogglingId(item._id)
    const newStatus = item.status === 'active' ? 'paused' : 'active'
    try {
      await APIClient.put(`/api/automations/${item._id}`, { status: newStatus })
      setAutomations((prev) =>
        prev.map((a) => (a._id === item._id ? { ...a, status: newStatus } : a))
      )
      toast.success(`Automation ${newStatus === 'active' ? 'resumed' : 'paused'}`)
      fetchStats()
    } catch (err: any) {
      toast.error(err?.message || 'Failed to update automation')
    } finally {
      setTogglingId(null)
    }
  }

  // ── Delete ────────────────────────────────────────────────────────────────────

  const confirmDelete = async () => {
    if (!deleteModal.item) return
    setDeletingId(deleteModal.item._id)
    try {
      await APIClient.delete(`/api/automations/${deleteModal.item._id}`)
      setAutomations((prev) => prev.filter((a) => a._id !== deleteModal.item!._id))
      toast.success('Automation deleted')
      setDeleteModal({ open: false, item: null })
      fetchStats()
    } catch (err: any) {
      toast.error(err?.message || 'Failed to delete automation')
    } finally {
      setDeletingId(null)
    }
  }

  // ── Stat cards ────────────────────────────────────────────────────────────────

  const statCards = [
    {
      label: 'Active Automations',
      value: stats?.total_active ?? '—',
      icon: <Zap className="w-5 h-5" />,
      color: 'text-violet-400',
      bg: 'bg-violet-950/40 border-violet-900/40',
    },
    {
      label: 'Upcoming Reminders',
      value: stats?.upcoming_reminders ?? '—',
      icon: <Bell className="w-5 h-5" />,
      color: 'text-blue-400',
      bg: 'bg-blue-950/40 border-blue-900/40',
    },
    {
      label: 'Interviews This Week',
      value: stats?.interviews_this_week ?? '—',
      icon: <Calendar className="w-5 h-5" />,
      color: 'text-emerald-400',
      bg: 'bg-emerald-950/40 border-emerald-900/40',
    },
    {
      label: 'Overdue Tasks',
      value: stats?.overdue_count ?? '—',
      icon: <AlertTriangle className="w-5 h-5" />,
      color: 'text-amber-400',
      bg: 'bg-amber-950/40 border-amber-900/40',
    },
  ]

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <AppLayout>
      <DeleteModal
        open={deleteModal.open}
        onClose={() => setDeleteModal({ open: false, item: null })}
        onConfirm={confirmDelete}
        company={deleteModal.item?.company ?? ''}
        type={deleteModal.item?.type ?? ''}
        loading={!!deletingId}
      />

      <div className="space-y-8 pb-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold mb-1 bg-gradient-to-r from-violet-400 to-blue-400 bg-clip-text text-transparent">
            Automation
          </h1>
          <p className="text-muted-foreground text-sm">
            Schedule smart reminders, interview notifications, and AI-powered prep — all running automatically.
          </p>
        </div>

        {/* ── Section A: Overview Stats ─────────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((card) => (
            <div
              key={card.label}
              className={`glass rounded-xl p-5 border ${card.bg} flex items-center gap-4 transition-all duration-300`}
            >
              <div className={`${card.color} shrink-0`}>{card.icon}</div>
              <div>
                <p className="text-xs text-muted-foreground leading-tight">{card.label}</p>
                {loadingStats ? (
                  <div className="h-7 w-10 mt-1 rounded bg-white/10 animate-pulse" />
                ) : (
                  <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
          {/* ── Section B: Create Automation Form ──────────────────────────── */}
          <div className="xl:col-span-2">
            <div className="glass rounded-2xl p-6 border border-white/10 h-full">
              <div className="flex items-center gap-2 mb-6">
                <div className="w-8 h-8 rounded-lg bg-violet-950/60 border border-violet-900/50 flex items-center justify-center">
                  <Plus className="w-4 h-4 text-violet-400" />
                </div>
                <h2 className="text-lg font-semibold">Create Automation</h2>
              </div>

              <form onSubmit={handleCreate} className="space-y-4">
                {/* Application picker */}
                <div>
                  <label className="block text-xs text-muted-foreground mb-1.5 font-medium">
                    Application
                  </label>
                  <select
                    value={form.application_id}
                    onChange={(e) => setForm((f) => ({ ...f, application_id: e.target.value }))}
                    className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50 transition-all"
                    required
                  >
                    <option value="" className="bg-slate-900">
                      — Select Application —
                    </option>
                    {applications.map((app) => (
                      <option key={app._id} value={app._id} className="bg-slate-900">
                        {app.company_name} – {app.role}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Type selector */}
                <div>
                  <label className="block text-xs text-muted-foreground mb-1.5 font-medium">
                    Automation Type
                  </label>
                  <div className="grid grid-cols-1 gap-2">
                    {(['followup', 'interview', 'status'] as const).map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, type: t }))}
                        className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm font-medium transition-all ${form.type === t
                          ? 'bg-violet-600/30 border-violet-500/60 text-violet-300'
                          : 'bg-white/5 border-white/10 text-muted-foreground hover:border-white/20'
                          }`}
                      >
                        <span className={form.type === t ? 'text-violet-400' : 'text-muted-foreground'}>
                          {TYPE_ICONS[t]}
                        </span>
                        {TYPE_LABELS[t]}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Date & time */}
                <div>
                  <label className="block text-xs text-muted-foreground mb-1.5 font-medium">
                    Scheduled Date & Time
                  </label>
                  <input
                    type="datetime-local"
                    value={form.scheduled_at}
                    onChange={(e) => setForm((f) => ({ ...f, scheduled_at: e.target.value }))}
                    className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500/50 transition-all [color-scheme:dark]"
                    required
                  />
                </div>

                {/* Toggles */}
                <div className="space-y-3 pt-1">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
                    <div className="flex items-center gap-2">
                      <Mail className="w-4 h-4 text-blue-400" />
                      <div>
                        <p className="text-sm font-medium">Email Notification</p>
                        <p className="text-xs text-muted-foreground">Send reminder via Gmail</p>
                      </div>
                    </div>
                    <Switch
                      checked={form.email_enabled}
                      onCheckedChange={(v) => setForm((f) => ({ ...f, email_enabled: v }))}
                    />
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
                    <div className="flex items-center gap-2">
                      <Bot className="w-4 h-4 text-violet-400" />
                      <div>
                        <p className="text-sm font-medium">AI Preparation Tips</p>
                        <p className="text-xs text-muted-foreground">Generate Gemini prep tips</p>
                      </div>
                    </div>
                    <Switch
                      checked={form.ai_prep_enabled}
                      onCheckedChange={(v) => setForm((f) => ({ ...f, ai_prep_enabled: v }))}
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={saving}
                  className="w-full bg-violet-600 hover:bg-violet-700 text-white border-0 shadow-lg shadow-violet-900/40 mt-2"
                >
                  {saving ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" /> Saving…
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4 mr-2" /> Save Automation
                    </>
                  )}
                </Button>
              </form>
            </div>
          </div>

          {/* ── Section C: Active Automations List ─────────────────────────── */}
          <div className="xl:col-span-3">
            <div className="glass rounded-2xl p-6 border border-white/10 h-full">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-blue-950/60 border border-blue-900/50 flex items-center justify-center">
                    <BriefcaseIcon className="w-4 h-4 text-blue-400" />
                  </div>
                  <h2 className="text-lg font-semibold">Active Automations</h2>
                </div>
                <button
                  onClick={() => { fetchStats(); fetchAutomations() }}
                  className="text-muted-foreground hover:text-white transition-colors p-1.5 rounded-lg hover:bg-white/10"
                  title="Refresh"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>

              {loadingList ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-24 rounded-xl bg-white/5 animate-pulse" />
                  ))}
                </div>
              ) : automations.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="w-16 h-16 rounded-full bg-violet-950/40 border border-violet-900/30 flex items-center justify-center mb-4">
                    <Zap className="w-7 h-7 text-violet-400/60" />
                  </div>
                  <p className="text-muted-foreground font-medium">No automations yet</p>
                  <p className="text-xs text-muted-foreground/60 mt-1">
                    Create your first automation using the form on the left
                  </p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1 custom-scrollbar">
                  {automations.map((item) => {
                    const isToggling = togglingId === item._id
                    return (
                      <div
                        key={item._id}
                        className={`group flex items-start gap-4 p-4 rounded-xl border transition-all duration-200 ${item.status === 'completed'
                          ? 'bg-white/[0.02] border-white/5 opacity-60'
                          : 'bg-white/5 border-white/10 hover:border-white/20 hover:bg-white/[0.07]'
                          }`}
                      >
                        {/* Type icon */}
                        <div className="w-9 h-9 rounded-lg bg-violet-950/60 border border-violet-900/40 flex items-center justify-center shrink-0 mt-0.5 text-violet-400">
                          {TYPE_ICONS[item.type]}
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2 flex-wrap">
                            <div>
                              <p className="font-semibold text-sm truncate">
                                {item.company}
                                <span className="text-muted-foreground font-normal"> · {item.role}</span>
                              </p>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {TYPE_LABELS[item.type]}
                              </p>
                            </div>
                            <StatusBadge status={item.status} scheduledAt={item.scheduled_at} />
                          </div>

                          <div className="flex items-center gap-3 mt-2 flex-wrap">
                            <span className="flex items-center gap-1 text-xs text-muted-foreground">
                              <Clock className="w-3 h-3" />
                              {new Date(item.scheduled_at.endsWith('Z') ? item.scheduled_at : item.scheduled_at + 'Z').toLocaleString('en-IN', {
                                month: 'short', day: 'numeric', year: 'numeric',
                                hour: '2-digit', minute: '2-digit',
                              })}
                            </span>
                            {item.email_enabled && (
                              <span className="flex items-center gap-1 text-xs text-blue-400">
                                <Mail className="w-3 h-3" /> Email ON
                              </span>
                            )}
                            {item.ai_prep_enabled && (
                              <span className="flex items-center gap-1 text-xs text-violet-400">
                                <Bot className="w-3 h-3" /> AI ON
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2 shrink-0">
                          {item.status !== 'completed' && (
                            <button
                              onClick={() => handleToggle(item)}
                              disabled={isToggling}
                              title={item.status === 'active' ? 'Pause' : 'Resume'}
                              className="p-1.5 rounded-lg text-muted-foreground hover:text-white hover:bg-white/10 transition-all disabled:opacity-50"
                            >
                              {isToggling ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : item.status === 'active' ? (
                                <ToggleRight className="w-4 h-4 text-emerald-400" />
                              ) : (
                                <ToggleLeft className="w-4 h-4 text-amber-400" />
                              )}
                            </button>
                          )}
                          <button
                            onClick={() => setDeleteModal({ open: true, item })}
                            title="Delete"
                            className="p-1.5 rounded-lg text-muted-foreground hover:text-red-400 hover:bg-red-950/40 transition-all"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
