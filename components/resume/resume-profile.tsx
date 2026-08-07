'use client'

import React, { useEffect, useState, useCallback } from 'react'
import {
  User, Mail, Phone, Linkedin, GraduationCap, Briefcase,
  FolderOpen, Award, Code2, RefreshCw, Trash2, FileText,
  ExternalLink, ChevronDown, ChevronUp, Zap, Clock, Hash,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { getResumeProfile, deleteResume, ResumeProfile } from '@/src/services/api'
import { API_URL } from '@/src/services/api'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/context/auth-context'

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SKILL_PALETTE = [
  'bg-violet-500/15 text-violet-300 border-violet-500/25',
  'bg-blue-500/15 text-blue-300 border-blue-500/25',
  'bg-cyan-500/15 text-cyan-300 border-cyan-500/25',
  'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
  'bg-amber-500/15 text-amber-300 border-amber-500/25',
  'bg-rose-500/15 text-rose-300 border-rose-500/25',
  'bg-indigo-500/15 text-indigo-300 border-indigo-500/25',
  'bg-teal-500/15 text-teal-300 border-teal-500/25',
]

function skillColor(index: number) {
  return SKILL_PALETTE[index % SKILL_PALETTE.length]
}

/** Collapsible list for long sections */
function CollapsibleList({ items, max = 3, renderItem }: {
  items: string[]
  max?: number
  renderItem: (item: string, i: number) => React.ReactNode
}) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? items : items.slice(0, max)

  return (
    <div className="space-y-2">
      {visible.map(renderItem)}
      {items.length > max && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="flex items-center gap-1 text-xs text-primary/70 hover:text-primary transition-colors mt-1"
        >
          {expanded ? (
            <><ChevronUp className="w-3 h-3" /> Show less</>
          ) : (
            <><ChevronDown className="w-3 h-3" /> Show {items.length - max} more</>
          )}
        </button>
      )}
    </div>
  )
}

// Section card wrapper
function Section({ icon, title, children }: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="glass rounded-xl p-5 glow">
      <h4 className="font-bold mb-4 flex items-center gap-2 text-sm uppercase tracking-wider text-muted-foreground border-b border-white/10 pb-3">
        <span className="text-primary">{icon}</span>
        {title}
      </h4>
      {children}
    </div>
  )
}

// Individual timeline card (experience / education / project)
function TimelineCard({ title, subtitle, detail }: {
  title: string
  subtitle?: string
  detail?: string
}) {
  return (
    <div className="flex gap-3 p-3 rounded-xl bg-black/20 border border-white/5 hover:bg-white/[0.04] transition-colors">
      <div className="mt-1 w-2 h-2 rounded-full bg-primary/60 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-white leading-snug break-words">{title}</p>
        {subtitle && <p className="text-xs text-primary/80 font-medium mt-0.5 truncate">{subtitle}</p>}
        {detail && <p className="text-xs text-gray-400 mt-1 leading-relaxed line-clamp-3">{detail}</p>}
      </div>
    </div>
  )
}

/** Robustly formats string OR object section items into title, subtitle, and detail */
function formatSectionItem(item: any): { title: string; subtitle?: string; detail?: string } {
  if (!item) return { title: '' }
  if (typeof item === 'string') return { title: item }
  if (typeof item === 'number' || typeof item === 'boolean') return { title: String(item) }

  if (typeof item === 'object') {
    // Education: { degree, institution, duration, location, grade }
    if (item.degree || item.institution || item.school || item.college || item.university) {
      const degree = item.degree || item.course || item.major || ''
      const inst = item.institution || item.school || item.college || item.university || ''
      const duration = item.duration || item.dates || item.year || item.years || ''
      const detail = [item.location, item.grade ? `Grade: ${item.grade}` : null].filter(Boolean).join(' • ')
      return {
        title: [degree, inst].filter(Boolean).join(' at ') || Object.values(item).filter(v => typeof v === 'string').join(' - '),
        subtitle: duration || undefined,
        detail: detail || undefined,
      }
    }

    // Experience: { title, role, company, organization, duration, dates, description, details }
    if (item.role || item.title || item.company || item.organization) {
      const role = item.role || item.title || item.position || ''
      const company = item.company || item.organization || item.employer || ''
      const duration = item.duration || item.dates || item.period || ''
      const desc = item.description || item.details || item.summary || ''
      return {
        title: [role, company].filter(Boolean).join(' at ') || role || company,
        subtitle: duration || undefined,
        detail: typeof desc === 'string' ? desc : Array.isArray(desc) ? desc.join('. ') : undefined,
      }
    }

    // Projects: { name, title, description, details, tech_stack }
    if (item.name || item.project || item.title) {
      const name = item.name || item.project || item.title || ''
      const desc = item.description || item.details || item.summary || ''
      const tech = item.tech_stack || item.technologies || item.skills || ''
      const subtitle = Array.isArray(tech) ? tech.join(', ') : typeof tech === 'string' ? tech : undefined
      return {
        title: name,
        subtitle,
        detail: typeof desc === 'string' ? desc : Array.isArray(desc) ? desc.join('. ') : undefined,
      }
    }

    // Certifications: { title, name, issuer, year, date }
    if (item.issuer || item.organization) {
      const name = item.name || item.title || item.certification || ''
      const issuer = item.issuer || item.organization || ''
      const date = item.year || item.date || ''
      return {
        title: [name, issuer].filter(Boolean).join(' — ') || name || issuer,
        subtitle: date || undefined,
      }
    }

    // Generic Object Fallback
    const vals = Object.values(item).filter(v => typeof v === 'string' || typeof v === 'number')
    if (vals.length > 0) {
      return { title: String(vals[0]), subtitle: vals.slice(1).join(' • ') }
    }
  }

  return { title: String(item) }
}

// ─── Loading Skeleton ──────────────────────────────────────────────────────────

function ProfileSkeleton() {
  return (
    <div className="space-y-5 animate-pulse">
      <div className="glass rounded-xl p-6 glow flex items-center gap-5">
        <Skeleton className="w-16 h-16 rounded-full shrink-0" />
        <div className="space-y-2 flex-1">
          <Skeleton className="h-6 w-2/5" />
          <Skeleton className="h-4 w-3/5" />
          <Skeleton className="h-4 w-1/3" />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Skeleton className="h-44 rounded-xl" />
        <Skeleton className="h-44 rounded-xl" />
        <Skeleton className="h-36 rounded-xl" />
        <Skeleton className="h-36 rounded-xl" />
      </div>
    </div>
  )
}

// ─── Empty State ───────────────────────────────────────────────────────────────

function EmptyState({ onUploadClick }: { onUploadClick?: () => void }) {
  return (
    <div className="glass rounded-xl p-12 glow flex flex-col items-center justify-center text-center gap-4">
      <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-2">
        <FileText className="w-8 h-8 text-primary/60" />
      </div>
      <h3 className="text-xl font-bold text-white">No Resume Stored Yet</h3>
      <p className="text-sm text-muted-foreground max-w-sm leading-relaxed">
        Upload a resume to get an AI-powered structured profile. Gemini will extract your skills,
        experience, education, projects, and certifications automatically.
      </p>
      <div className="mt-2 flex flex-wrap gap-3 justify-center text-xs text-muted-foreground/60">
        <span className="flex items-center gap-1"><Code2 className="w-3 h-3" />Skills extracted</span>
        <span className="flex items-center gap-1"><Briefcase className="w-3 h-3" />Experience mapped</span>
        <span className="flex items-center gap-1"><GraduationCap className="w-3 h-3" />Education parsed</span>
        <span className="flex items-center gap-1"><FolderOpen className="w-3 h-3" />Projects listed</span>
      </div>
    </div>
  )
}

// ─── Main Export ──────────────────────────────────────────────────────────────

interface ResumeProfileProps {
  /** When `true`, the component auto-refetches (useful after an upload) */
  refetchSignal?: number
}

export function ResumeProfileCard({ refetchSignal }: ResumeProfileProps) {
  const { refreshUser } = useAuth()
  const [profile, setProfile] = useState<ResumeProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [activeTab, setActiveTab] = useState<'parsed' | 'raw'>('parsed')

  const fetchProfile = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    try {
      const data = await getResumeProfile()
      setProfile(data)
    } catch {
      setProfile(null)
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [])

  const handleManualRefresh = async () => {
    setLoading(true)
    try {
      const data = await getResumeProfile()
      setProfile(data)
      await refreshUser()
      toast.success('✓ Resume profile refreshed')
    } catch {
      setProfile(null)
      toast.error('Failed to refresh resume profile')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProfile()
  }, [fetchProfile, refetchSignal])

  // Polling effect: while status === 'pending', re-check profile status every 3s
  useEffect(() => {
    if (profile?.status === 'pending') {
      const interval = setInterval(() => {
        fetchProfile(true)
      }, 3000)
      return () => clearInterval(interval)
    }
  }, [profile?.status, fetchProfile])

  const handleConfirmDelete = async (e?: React.SyntheticEvent) => {
    e?.preventDefault()
    setDeleting(true)
    setShowDeleteModal(false)
    try {
      await deleteResume()
      setProfile(null)
      await refreshUser()
      toast.success('✓ Resume removed and match analysis records cleared')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to delete resume')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <ProfileSkeleton />
  if (!profile) return <EmptyState />

  const p = profile.parsed_json ?? {}
  const hasParsed = Object.keys(p).length > 0

  // Safely normalise each field to array (string or object)
  const skills: string[] = Array.isArray(p.skills)
    ? p.skills.map((s: any) => typeof s === 'string' ? s : (s?.name || s?.skill || Object.values(s || {}).filter(v => typeof v === 'string').join(' '))).filter(Boolean)
    : []
  const education: any[] = Array.isArray(p.education) ? p.education.filter(Boolean) : []
  const experience: any[] = Array.isArray(p.experience) ? p.experience.filter(Boolean) : []
  const projects: any[] = Array.isArray(p.projects) ? p.projects.filter(Boolean) : []
  const certifications: any[] = Array.isArray(p.certifications) ? p.certifications.filter(Boolean) : []

  const uploadedDate = profile.uploaded_at
    ? new Date(profile.uploaded_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : null

  return (
    <div className="space-y-5 animate-in fade-in duration-500">

      {/* ── Header card ─────────────────────────────────────────────────── */}
      <div className="glass rounded-xl p-6 glow relative overflow-hidden">
        {/* Glow blob */}
        <div className="absolute top-0 right-0 w-64 h-64 opacity-5 blur-3xl rounded-full translate-x-1/3 -translate-y-1/3 bg-primary" />

        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
          {/* Avatar placeholder with initials */}
          <div className="w-16 h-16 rounded-2xl bg-primary/15 border border-primary/25 flex items-center justify-center text-2xl font-bold text-primary shrink-0">
            {p.name ? p.name.charAt(0).toUpperCase() : '?'}
          </div>

          <div className="flex-1 min-w-0">
            <h2 className="text-2xl font-bold text-white truncate">
              {p.name || 'Name not extracted'}
            </h2>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
              {p.email && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Mail className="w-3.5 h-3.5 text-primary/60" />
                  <span className="truncate max-w-[220px]">{p.email}</span>
                </span>
              )}
              {p.phone && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Phone className="w-3.5 h-3.5 text-primary/60" />
                  {p.phone}
                </span>
              )}
              {p.linkedin && (
                <a
                  href={p.linkedin.startsWith('http') ? p.linkedin : `https://${p.linkedin}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  <Linkedin className="w-3.5 h-3.5" />
                  LinkedIn ↗
                </a>
              )}
            </div>
            <div className="flex flex-wrap gap-3 mt-3">
              {uploadedDate && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground/60">
                  <Clock className="w-3 h-3" />
                  Uploaded {uploadedDate}
                </span>
              )}
              {profile.resume_version && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground/60">
                  <Hash className="w-3 h-3" />
                  v{profile.resume_version}
                </span>
              )}
              {profile.file_url && (
                <a
                  href={`${API_URL}${profile.file_url}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-blue-400/70 hover:text-blue-400 transition-colors"
                >
                  <ExternalLink className="w-3 h-3" />
                  View original file ↗
                </a>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 shrink-0 self-start">
            <Button
              variant="outline"
              size="sm"
              onClick={handleManualRefresh}
              disabled={loading || deleting}
              className="h-8 text-xs gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowDeleteModal(true)}
              disabled={deleting}
              className="h-8 text-xs gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete
            </Button>
          </div>
        </div>

        {/* ── Background Parsing Banner ───────────────────────────────────── */}
        {profile.status === 'pending' && (
          <div className="mt-4 p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 flex items-center gap-3 animate-pulse">
            <RefreshCw className="w-5 h-5 animate-spin text-amber-400 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-amber-200">AI Resume Parsing in Progress...</p>
              <p className="text-xs text-amber-300/80 mt-0.5">
                Your file is stored. Gemini is extracting your skills and experience in the background — this profile will auto-update in a few seconds.
              </p>
            </div>
          </div>
        )}

        {profile.status === 'failed' && (
          <div className="mt-4 p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-200 flex items-center gap-3">
            <Zap className="w-5 h-5 text-rose-400 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-rose-200">Resume parsing failed</p>
              <p className="text-xs text-rose-300/70 mt-0.5">
                {profile.parse_error
                  ? `AI error: ${profile.parse_error}`
                  : 'AI extraction could not process this file. Check the Raw Text tab — if content is visible, try re-uploading.'}
              </p>
            </div>
          </div>
        )}

        {profile.status === 'parsed' && profile.parse_error && (
          <div className="mt-4 p-4 rounded-xl border border-yellow-500/30 bg-yellow-500/10 text-yellow-200 flex items-center gap-3">
            <Zap className="w-5 h-5 text-yellow-400 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-yellow-200">AI extraction partially succeeded</p>
              <p className="text-xs text-yellow-300/70 mt-0.5">
                Some fields (skills, email) were extracted via text fallback. Full AI parsing encountered an issue.
                Raw Text tab shows the original content.
              </p>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mt-5 p-1 bg-black/30 rounded-lg w-fit">
          {(['parsed', 'raw'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-all ${
                activeTab === tab
                  ? 'bg-primary text-white shadow-sm shadow-primary/30'
                  : 'text-muted-foreground hover:text-white'
              }`}
            >
              {tab === 'parsed' ? '✦ Structured View' : '⌗ Raw Text'}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab: Raw text ───────────────────────────────────────────────── */}
      {activeTab === 'raw' && (
        <div className="glass rounded-xl p-6 glow animate-in fade-in duration-300">
          <h4 className="font-bold mb-3 flex items-center gap-2 text-sm uppercase tracking-wider text-muted-foreground">
            <FileText className="w-4 h-4 text-primary" />
            Raw Extracted Text
          </h4>
          <pre className="whitespace-pre-wrap font-mono text-xs text-gray-300 leading-relaxed max-h-[60vh] overflow-y-auto p-4 bg-black/30 rounded-lg border border-white/5">
            {profile.raw_text || 'No raw text available.'}
          </pre>
        </div>
      )}

      {/* ── Tab: Parsed structured view ─────────────────────────────────── */}
      {activeTab === 'parsed' && (
        <>
          {!hasParsed && (
            <div className="glass rounded-xl p-6 glow text-center animate-in fade-in">
              <Zap className="w-8 h-8 text-yellow-400/60 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                No structured data was extracted.
              </p>
              <p className="text-xs text-muted-foreground/60 mt-1">
                This is usually caused by an AI API issue — not a scanned PDF. Check the Raw Text tab below; if text is visible, try re-uploading or refreshing.
              </p>
            </div>
          )}

          {hasParsed && !p.name && (
            <div className="glass rounded-xl p-4 border border-yellow-500/30 bg-yellow-500/10 animate-in fade-in flex items-start gap-3 mb-2">
              <Zap className="w-4 h-4 text-yellow-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-yellow-200">Name could not be extracted</p>
                <p className="text-xs text-yellow-300/70 mt-0.5">
                  AI parsing may have partially succeeded — skills and contact info may still be shown below.
                  Check the Raw Text tab for full content.
                </p>
              </div>
            </div>
          )}

          {hasParsed && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 animate-in fade-in duration-400">

              {/* Skills */}
              {skills.length > 0 && (
                <div className="glass rounded-xl p-5 glow md:col-span-2">
                  <h4 className="font-bold mb-4 flex items-center gap-2 text-sm uppercase tracking-wider text-muted-foreground border-b border-white/10 pb-3">
                    <span className="text-primary"><Code2 className="w-4 h-4" /></span>
                    Technical Skills
                    <span className="ml-auto text-xs font-normal normal-case bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                      {skills.length} total
                    </span>
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {skills.map((skill, i) => (
                      <span
                        key={i}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all hover:scale-105 cursor-default ${skillColor(i)}`}
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Education */}
              {education.length > 0 && (
                <Section icon={<GraduationCap className="w-4 h-4" />} title="Education">
                  <CollapsibleList
                    items={education}
                    max={3}
                    renderItem={(item, i) => {
                      const f = formatSectionItem(item)
                      return <TimelineCard key={i} title={f.title} subtitle={f.subtitle} detail={f.detail} />
                    }}
                  />
                </Section>
              )}

              {/* Experience */}
              {experience.length > 0 && (
                <Section icon={<Briefcase className="w-4 h-4" />} title="Experience">
                  <CollapsibleList
                    items={experience}
                    max={3}
                    renderItem={(item, i) => {
                      const f = formatSectionItem(item)
                      return <TimelineCard key={i} title={f.title} subtitle={f.subtitle} detail={f.detail} />
                    }}
                  />
                </Section>
              )}

              {/* Projects */}
              {projects.length > 0 && (
                <Section icon={<FolderOpen className="w-4 h-4" />} title="Projects">
                  <CollapsibleList
                    items={projects}
                    max={4}
                    renderItem={(item, i) => {
                      const f = formatSectionItem(item)
                      return <TimelineCard key={i} title={f.title} subtitle={f.subtitle} detail={f.detail} />
                    }}
                  />
                </Section>
              )}

              {/* Certifications */}
              {certifications.length > 0 && (
                <Section icon={<Award className="w-4 h-4" />} title="Certifications">
                  <CollapsibleList
                    items={certifications}
                    max={3}
                    renderItem={(item, i) => {
                      const f = formatSectionItem(item)
                      return (
                        <div key={i} className="flex items-center gap-3 p-3 rounded-xl bg-black/20 border border-white/5 hover:bg-white/[0.04] transition-colors">
                          <Award className="w-4 h-4 text-amber-400/80 shrink-0" />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm text-gray-200 font-medium leading-snug">{f.title}</p>
                            {f.subtitle && <p className="text-xs text-muted-foreground mt-0.5">{f.subtitle}</p>}
                          </div>
                        </div>
                      )
                    }}
                  />
                </Section>
              )}

            </div>
          )}
        </>
      )}

      {/* ── Radix Delete Confirmation Modal ─────────────────────────── */}
      <AlertDialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <AlertDialogContent className="glass border-white/10 bg-slate-950/95 text-white max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-xl font-bold flex items-center gap-2 text-rose-400">
              <Trash2 className="w-5 h-5" /> Delete Resume & Analysis Data?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-sm text-muted-foreground leading-relaxed mt-2">
              This action is <strong className="text-rose-300">destructive</strong>. It will permanently remove your stored resume file from physical storage, clear your profile linkage, and invalidate all past job match analysis records.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-6 gap-2">
            <AlertDialogCancel className="bg-white/5 border-white/10 text-white hover:bg-white/10">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              disabled={deleting}
              className="bg-rose-600 text-white hover:bg-rose-700 shadow-md shadow-rose-600/30"
            >
              {deleting ? 'Deleting...' : '✓ Delete Resume'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
