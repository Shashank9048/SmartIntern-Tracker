'use client'

import { Lightbulb, Loader2, RefreshCw, TrendingUp, BookOpen, Bell, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getDashboardInsights, type DashboardInsights } from '@/src/services/api'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'

export function AIInsights() {
  const [insights, setInsights] = useState<DashboardInsights | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchInsights = async () => {
    setLoading(true)
    try {
      const data = await getDashboardInsights()
      setInsights(data)
    } catch (error) {
      // getDashboardInsights already returns null for network errors.
      // Only show toast for actual API errors (not offline/unreachable).
      const isNetworkErr = error instanceof TypeError ||
        (error instanceof Error && (error.message === 'Failed to fetch' || error.message.startsWith('NetworkError')))
      if (!isNetworkErr) {
        toast.error('Failed to load AI Insights')
        console.warn('[AIInsights] Error:', error)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchInsights()
  }, [])

  return (
    <div className="glass rounded-xl p-6 glow">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Lightbulb className="w-5 h-5 text-accent" />
          <h3 className="text-lg font-semibold">AI Career Insights</h3>
          <span className="text-xs bg-accent/10 text-accent px-2 py-0.5 rounded-full border border-accent/20">Powered by Gemini</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={fetchInsights}
          disabled={loading}
          title="Refresh Insights"
          className="h-8 w-8 hover:bg-white/10"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-10 gap-3 text-muted-foreground">
          <Loader2 className="w-8 h-8 animate-spin" />
          <p className="text-sm">Gemini is analyzing your applications...</p>
        </div>
      ) : !insights ? (
        <p className="text-gray-400 text-center py-6 text-sm">No apps tracked yet — add applications first to unlock AI insights!</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {/* Trends */}
          <div className="p-4 rounded-xl bg-white/5 border border-white/5 hover:border-primary/20 transition-colors col-span-full">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              <h4 className="text-sm font-bold text-white">Application Trends</h4>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">{insights.trends}</p>
          </div>

          {/* Improvement Strategy */}
          <div className="p-4 rounded-xl bg-white/5 border border-white/5 hover:border-yellow-500/20 transition-colors">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="w-4 h-4 text-yellow-400" />
              <h4 className="text-sm font-bold text-white">Improvement Strategy</h4>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">{insights.improvement_strategy}</p>
          </div>

          {/* Learning Roadmap */}
          <div className="p-4 rounded-xl bg-white/5 border border-white/5 hover:border-blue-500/20 transition-colors">
            <div className="flex items-center gap-2 mb-2">
              <BookOpen className="w-4 h-4 text-blue-400" />
              <h4 className="text-sm font-bold text-white">Learning Roadmap</h4>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">{insights.learning_roadmap}</p>
          </div>

          {/* Follow-up Suggestions */}
          {insights.follow_up_suggestions && insights.follow_up_suggestions.length > 0 && (
            <div className="p-4 rounded-xl bg-white/5 border border-white/5 hover:border-green-500/20 transition-colors col-span-full">
              <div className="flex items-center gap-2 mb-3">
                <Bell className="w-4 h-4 text-green-400" />
                <h4 className="text-sm font-bold text-white">Follow-up Suggestions</h4>
              </div>
              <ul className="space-y-2">
                {insights.follow_up_suggestions.map((suggestion, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-400 mt-1.5 shrink-0" />
                    {suggestion}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
