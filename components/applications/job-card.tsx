'use client'

import { Button } from '@/components/ui/button'
import { MapPin, Building2, Calendar, ExternalLink, Bookmark } from 'lucide-react'
import { RecommendedJobEntry } from '@/types'

interface JobCardProps {
  entry: RecommendedJobEntry
}

/** Colour-coded score badge */
function ScoreBadge({ score }: { score: number }) {
  const colour =
    score >= 85
      ? 'text-amber-400'
      : score >= 70
      ? 'text-amber-300'
      : 'text-amber-200/70'

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
  // Show at most 4 matched + 4 missing to keep card compact
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

export function JobCard({ entry }: JobCardProps) {
  const { job, match_score, matched_skills, missing_skills } = entry

  const postedDate = job.posted_at
    ? new Date(job.posted_at).toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
      })
    : null

  return (
    <div className="glass rounded-2xl p-5 flex flex-col gap-3 min-w-[300px] max-w-[340px] shrink-0 hover:bg-white/10 transition-all duration-300 border border-white/10 hover:border-amber-400/20 hover:shadow-lg hover:shadow-amber-400/5 group">
      {/* Top row: title + score */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
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
          className="h-full rounded-full bg-gradient-to-r from-amber-500 to-amber-300 transition-all duration-700"
          style={{ width: `${match_score}%` }}
        />
      </div>

      {/* Skill diff */}
      <SkillDiff matched={matched_skills} missing={missing_skills} />

      {/* Actions — disabled until Phase 6 */}
      <div className="flex gap-2 mt-auto pt-1">
        <div className="relative flex-1 group/tip">
          <Button
            size="sm"
            disabled
            className="w-full bg-amber-500/10 text-amber-400/50 border border-amber-400/10 cursor-not-allowed hover:bg-amber-500/10"
            aria-label="Apply — Coming in Phase 6"
          >
            <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
            Apply
          </Button>
          <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded bg-black/80 text-white text-xs whitespace-nowrap opacity-0 group-hover/tip:opacity-100 transition-opacity z-10">
            Coming in Phase 6
          </span>
        </div>
        <div className="relative flex-1 group/tip2">
          <Button
            size="sm"
            disabled
            variant="outline"
            className="w-full border-white/10 text-white/30 cursor-not-allowed hover:bg-transparent"
            aria-label="Save — Coming in Phase 6"
          >
            <Bookmark className="w-3.5 h-3.5 mr-1.5" />
            Save
          </Button>
          <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 rounded bg-black/80 text-white text-xs whitespace-nowrap opacity-0 group-hover/tip2:opacity-100 transition-opacity z-10">
            Coming in Phase 6
          </span>
        </div>
      </div>
    </div>
  )
}
