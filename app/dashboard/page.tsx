'use client'

import React, { useEffect, useState } from 'react'
import { AppLayout } from '@/components/app-layout'
import { SummaryCard } from '@/components/dashboard/summary-card'
import { AIInsights } from '@/components/dashboard/ai-insights'
import { ResumeUpload } from '@/components/dashboard/resume-upload'
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Briefcase, CheckCircle, Mail, ThumbsDown } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useApplicationContext } from '@/context/application-context'

export default function DashboardPage() {
  const { theme } = useTheme()
  const { stats, loading } = useApplicationContext()

  const chartTextColor = theme === 'dark' ? '#e0e7ff' : '#0f172a'

  const statusData = [
    { name: 'Applied', value: stats.total - stats.interviews - stats.offers - stats.rejected, color: '#6366f1' },
    { name: 'Interview', value: stats.interviews, color: '#a855f7' },
    { name: 'Selected', value: stats.offers, color: '#00d9ff' },
    { name: 'Rejected', value: stats.rejected, color: '#64748b' },
  ].filter(item => item.value > 0) // Only show non-zero values in pie chart

  return (
    <AppLayout>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold mb-2">Dashboard</h1>
          <p className="text-muted-foreground">
            Track your internship applications at a glance
          </p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <SummaryCard
            title="Total Applications"
            value={stats.total}
            icon={Mail}
            color="primary"
          />
          <SummaryCard
            title="Interviews"
            value={stats.interviews}
            icon={Briefcase}
            color="secondary"
          />
          <SummaryCard
            title="Offers"
            value={stats.offers}
            icon={CheckCircle}
            color="accent"
          />
          <SummaryCard
            title="Rejections"
            value={stats.rejected}
            icon={ThumbsDown}
            color="primary"
          />
        </div>

        {/* Charts and Resume Analysis side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 glass rounded-xl p-6 glow">
            <h3 className="text-lg font-semibold mb-4">
              Applications per Month
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={stats.chartData.length > 0 ? stats.chartData : [{ month: 'No Data', applications: 0 }]}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.1)"
                />
                <XAxis dataKey="month" stroke={chartTextColor} />
                <YAxis stroke={chartTextColor} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: theme === 'dark' ? '#1e293b' : '#f1f5f9',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="applications" fill="#6366f1" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-6">
            <div className="glass rounded-xl p-6 glow w-full">
              <h3 className="text-lg font-semibold mb-4">Status Distribution</h3>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={statusData.length > 0 ? statusData : [{ name: 'No Data', value: 1, color: '#333' }]}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    outerRadius={70}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {(statusData.length > 0 ? statusData : [{ name: 'No Data', value: 1, color: '#333' }]).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: theme === 'dark' ? '#1e293b' : '#f1f5f9',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '8px',
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <ResumeUpload />
            <RecentAnalysisCard />
          </div>
        </div>

        {/* AI Insights */}
        <AIInsights />
      </div>
    </AppLayout>
  )
}

function RecentAnalysisCard() {
  const [latestAnalysis, setLatestAnalysis] = useState<any>(null);
  useEffect(() => {
    import('@/src/services/api').then(({ getLatestAnalysis }) => {
      getLatestAnalysis().then(res => {
        if (res) setLatestAnalysis(res);
      })
    })
  }, []);

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-500'
    if (score >= 50) return 'text-yellow-500'
    return 'text-red-500'
  }

  if (!latestAnalysis) {
    return (
      <div className="glass rounded-xl p-6 glow flex flex-col items-center justify-center text-center h-40">
        <p className="text-sm text-muted-foreground mb-3">No recent resume analysis found.</p>
        <a href="/resume" className="text-xs bg-primary/20 text-primary px-3 py-1.5 rounded-md hover:bg-primary/30 transition-colors">
          Analyze Resume
        </a>
      </div>
    )
  }

  return (
    <div className="glass rounded-xl p-5 glow relative overflow-hidden flex flex-col h-fit">
      <h3 className="text-sm font-semibold mb-3 flex items-center justify-between">
        Latest Resume Match
        <span className={`text-lg font-bold ${getScoreColor(latestAnalysis.overall_match_score)}`}>{latestAnalysis.overall_match_score}%</span>
      </h3>
      <p className="text-xs text-muted-foreground line-clamp-2 mb-3">
        {latestAnalysis.job_description || "Score against recent Job Description"}
      </p>
      <div className="flex gap-2 mb-4 flex-wrap">
        <span className="text-[10px] bg-white/5 border border-white/10 px-2 py-0.5 rounded">
          Experience: <span className={latestAnalysis.experience_alignment === 'High' ? 'text-green-400' : 'text-yellow-400'}>{latestAnalysis.experience_alignment}</span>
        </span>
        <span className="text-[10px] bg-white/5 border border-white/10 px-2 py-0.5 rounded">
          ATS: {latestAnalysis.ats_score || latestAnalysis.overall_match_score}
        </span>
      </div>

      <a href="/resume" className="text-xs text-center border border-white/10 hover:border-white/20 bg-white/5 hover:bg-white/10 rounded-md py-2 transition-all w-full mt-auto">
        View Full Details
      </a>
    </div>
  )
}
