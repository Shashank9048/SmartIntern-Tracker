'use client';



import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { MoreVertical, Trash2, Edit2 } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ApplicationStatus } from '@/types'
import { useRouter } from 'next/navigation'

interface ApplicationCardProps {
  id: string
  company_name: string
  role: string
  status: ApplicationStatus
  applied_date: string
  interview_date?: string
  matchScore?: number
  onDelete?: () => void
  onEdit?: () => void
  onFollowUp?: () => void
  onUpdate?: (data: any) => void
}

const statusStyles: Record<ApplicationStatus, string> = {
  Applied: 'bg-blue-500/20 text-blue-400',
  Interview: 'bg-yellow-500/20 text-yellow-400',
  Selected: 'bg-green-500/20 text-green-400',
  Rejected: 'bg-red-500/20 text-red-500',
}

export function ApplicationCard({
  id,
  company_name,
  role,
  status,
  applied_date,
  interview_date,
  matchScore,
  onDelete,
  onEdit,
  onFollowUp,
}: ApplicationCardProps) {
  const router = useRouter()
  return (
    <div className="glass rounded-xl p-6 glow hover:bg-white/10 transition-all duration-300 h-full flex flex-col">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0 pr-4">
          <h3 className="text-lg font-semibold mb-1 truncate">{company_name}</h3>
          <p className="text-sm text-muted-foreground line-clamp-2">{role}</p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 hover:bg-white/10"
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="bg-card border-white/10">
            <DropdownMenuItem
              onClick={onEdit}
              className="cursor-pointer hover:bg-white/10"
            >
              <Edit2 className="w-4 h-4 mr-2" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={onDelete}
              className="cursor-pointer text-red-400 hover:bg-red-500/10"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex flex-col gap-1 mb-4">
        <div className="flex items-center justify-between">
          <Badge className={statusStyles[status] || 'bg-white/10 text-white'}>{status}</Badge>
          <span className="text-sm text-muted-foreground">Applied: {new Date(applied_date).toLocaleDateString()}</span>
        </div>
        {interview_date && (
          <div className="flex items-center justify-between mt-1">
            <span className="text-xs font-semibold text-yellow-400/80">Interview</span>
            <span className="text-xs text-yellow-400/80">{new Date(interview_date).toLocaleDateString()}</span>
          </div>
        )}
      </div>

      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">Match Score</span>
          {matchScore != null ? (
            <span className={`text-sm font-semibold ${matchScore >= 70 ? 'text-green-400' : matchScore >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
              {matchScore}%
            </span>
          ) : (
            <span className="text-xs text-muted-foreground px-2 py-0.5 rounded-full border border-white/10 bg-white/5">
              Pending AI
            </span>
          )}
        </div>
        {matchScore != null ? (
          <div className="w-full bg-white/10 rounded-full h-2">
            <div
              className={`h-2 rounded-full ${matchScore >= 70 ? 'bg-gradient-to-r from-green-500 to-emerald-400' : matchScore >= 50 ? 'bg-gradient-to-r from-yellow-500 to-orange-400' : 'bg-gradient-to-r from-red-500 to-red-400'}`}
              style={{ width: `${matchScore}%` }}
            />
          </div>
        ) : (
          <div className="w-full bg-white/10 rounded-full h-2 overflow-hidden">
            <div className="h-full w-1/3 bg-white/20 rounded-full animate-pulse" />
          </div>
        )}
      </div>

      <div className="flex gap-2 mt-auto">
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push(`/applications/${id}`)}
          className="flex-1 border-white/10 hover:bg-white/5 bg-transparent"
        >
          View Details
        </Button>
        <Button size="sm" onClick={onFollowUp} className="flex-1 bg-primary/20 text-primary hover:bg-primary/30">
          Follow Up
        </Button>
      </div>
    </div>
  )
}
