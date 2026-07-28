'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { MapPin, Building2, Calendar, ExternalLink, Bookmark, Check } from 'lucide-react'
import { RecommendedJobEntry } from '@/types'
import { toast } from 'sonner'

interface JobCardProps {
  entry: RecommendedJobEntry
  /** Called after a successful Save (wishlist) or Apply action */
  onApply?: (jobId: string) => void
  onSave?: (jobId: string) => void
  /** True when this job is already tracked in the kanban */
  isTracked?: boolean
}

/** Colour-coded score badge — amber for ≥70, dimmer for lower */
function ScoreBadge({ score }: { score: number }) {
  const colour =
    score >= 85
      ? 'text-amber-400'
      : score >= 70
      ? 'text-amber-300'
      : score >= 50
      ? 'text-amber-200/70'
      : 'text-white/40'

  return (
    <div className="flex flex-col items-end shrink-0">
      <span
        className={`font-mono text-3xl font-bold tabular-nums leading-none ${colour}`}
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {score}
      </span>
      <span
        className="text-xs text-muted-foreground mt-0.5 font-mono"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        % match
      </span>
    </div>
  )
}

/** +skill / −skill diff chips */
function SkillDiff({
  matched,
  missing,
}: {
  matched: string[]
  missing: string[]
}) {
  const showMatched = matched.slice(0, 4)
  const showMissing = missing.slice(0, 4)
  const extraMatched = matched.length - showMatched.length
  const extraMissing = missing.length - showMissing.length

  return (
    <div className="flex flex-wrap gap-1.5 mt-3">
      {showMatched.map((skill) => (
        <span
          key={`m-${skill}`}
          className="px-2 py-0.5 rounded text-xs font-mono bg-amber-400/10 text-amber-400 border border-amber-400/20"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          +{skill}
        </span>
      ))}
      {extraMatched > 0 && (
        <span
          className="px-2 py-0.5 rounded text-xs font-mono bg-amber-400/5 text-amber-400/60 border border-amber-400/10"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          +{extraMatched} more
        </span>
      )}
      {showMissing.map((skill) => (
        <span
          key={`x-${skill}`}
          className="px-2 py-0.5 rounded text-xs font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          −{skill}
        </span>
      ))}
      {extraMissing > 0 && (
        <span
          className="px-2 py-0.5 rounded text-xs font-mono bg-rose-500/5 text-rose-400/60 border border-rose-500/10"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          −{extraMissing} more
        </span>
      )}
    </div>
  )
}

export function JobCard({ entry, onApply, onSave, isTracked = false }: JobCardProps) {
  const { job, match_score, matched_skills, missing_skills, job_id } = entry
  const [actioning, setActioning] = useState<'apply' | 'save' | null>(null)
  const [tracked, setTracked] = useState(isTracked)
  const [trackedAs, setTrackedAs] = useState<'applied' | 'wishlist' | null>(null)

  const postedDate = job.posted_at
    ? new Date(job.posted_at).toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
      })
    : null

  const handleApply = () => {
    if (actioning || tracked) return

    if (!job.application_url || !job.application_url.trim()) {
      console.warn('[JobCard] Missing application_url for job:', job_id, job.title)
      toast.error('No application link for this listing', {
        style: {
          background: '#09090b',
          border: '1px solid rgba(244, 63, 94, 0.2)', // rose-500/20
          color: '#f43f5e',
          fontFamily: "'JetBrains Mono', monospace",
        },
      })
      return
    }

    const rawUrl = job.application_url.trim()
    const targetUrl =
      rawUrl.startsWith('http://') || rawUrl.startsWith('https://')
        ? rawUrl
        : `https://${rawUrl}`

    // 1. Open tab synchronously inside user gesture handler BEFORE any async await
    window.open(targetUrl, '_blank', 'noopener,noreferrer')
    
    // Update local card UI state immediately
    setTracked(true)
    setTrackedAs('applied')

    // 2. Fire tracking call in parallel (non-blocking)
    if (onApply) {
      setActioning('apply')
      Promise.resolve(onApply(job_id))
        .catch((err) => {
          console.error('[JobCard] Background application tracking failed:', err)
          toast.error('Application opened, but failed to save tracking record.')
        })
        .finally(() => {
          setActioning(null)
        })
    }
  }

  const handleSave = async () => {
    if (actioning || tracked) return
    setActioning('save')
    try {
      onSave?.(job_id)
      setTracked(true)
      setTrackedAs('wishlist')
    } finally {
      setActioning(null)
    }
  }

  return (
    <div
      className={`glass rounded-2xl p-5 flex flex-col gap-3 min-w-[300px] max-w-[340px] shrink-0 transition-all duration-300 border group relative
        ${tracked
          ? 'border-emerald-500/30 bg-emerald-500/5'
          : 'border-white/10 hover:bg-white/10 hover:border-amber-400/20 hover:shadow-lg hover:shadow-amber-400/5'
        }`}
    >
      {/* Tracked badge overlay */}
      {tracked && (
        <div className="absolute top-3 right-3 flex items-center gap-1 bg-emerald-500/20 border border-emerald-500/30 rounded-full px-2 py-0.5">
          <Check className="w-3 h-3 text-emerald-400" />
          <span className="text-xs text-emerald-400 font-mono" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {trackedAs === 'applied' ? 'Applied' : 'Saved'}
          </span>
        </div>
      )}

      {/* Top row: title + score */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0 pr-12">
          <h3
            className="text-base font-semibold leading-snug truncate text-white group-hover:text-amber-50 transition-colors"
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}
          >
            {job.title}
          </h3>
          <div className="flex items-center gap-1.5 mt-1">
            <Building2 className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
            <span className="text-sm text-muted-foreground truncate">{job.company}</span>
          </div>
        </div>
        <ScoreBadge score={match_score} />
      </div>

      {/* Location + date */}
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <MapPin className="w-3 h-3 shrink-0" />
          <span className="truncate max-w-[140px]">{job.location}</span>
        </div>
        {postedDate && (
          <div className="flex items-center gap-1 shrink-0">
            <Calendar className="w-3 h-3" />
            <span>{postedDate}</span>
          </div>
        )}
      </div>

      {/* Score bar */}
      <div className="w-full bg-white/10 rounded-full h-1.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${
            tracked
              ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
              : 'bg-gradient-to-r from-amber-500 to-amber-300'
          }`}
          style={{ width: `${match_score}%` }}
        />
      </div>

      {/* Skill diff */}
      <SkillDiff matched={matched_skills} missing={missing_skills} />

      {/* Actions */}
      <div className="flex gap-2 mt-auto pt-1">
        <Button
          size="sm"
          onClick={handleApply}
          disabled={!!actioning || tracked}
          className={`flex-1 transition-all ${
            tracked
              ? 'bg-emerald-500/10 text-emerald-400/50 border border-emerald-500/10 cursor-not-allowed'
              : 'bg-amber-500/15 text-amber-400 border border-amber-400/20 hover:bg-amber-500/25 hover:border-amber-400/40'
          }`}
        >
          {actioning === 'apply' ? (
            <span className="animate-pulse">…</span>
          ) : tracked && trackedAs === 'applied' ? (
            <><Check className="w-3.5 h-3.5 mr-1.5" />Applied</>
          ) : (
            <><ExternalLink className="w-3.5 h-3.5 mr-1.5" />Apply</>
          )}
        </Button>
        <Button
          size="sm"
          onClick={handleSave}
          disabled={!!actioning || tracked}
          variant="outline"
          className={`flex-1 transition-all ${
            tracked
              ? 'border-white/5 text-white/20 cursor-not-allowed hover:bg-transparent'
              : 'border-white/10 hover:bg-white/5 hover:border-white/20'
          }`}
        >
          {actioning === 'save' ? (
            <span className="animate-pulse">…</span>
          ) : tracked && trackedAs === 'wishlist' ? (
            <><Check className="w-3.5 h-3.5 mr-1.5" />Saved</>
          ) : (
            <><Bookmark className="w-3.5 h-3.5 mr-1.5" />Save</>
          )}
        </Button>
      </div>
    </div>
  )
}
