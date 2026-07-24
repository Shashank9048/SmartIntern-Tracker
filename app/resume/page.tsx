'use client'

import { useState, useCallback } from 'react'
import { AppLayout } from '@/components/app-layout'
import { ResumeAnalyzer } from '@/components/resume/resume-analyzer'
import { ResumeProfileCard } from '@/components/resume/resume-profile'
import { User, Zap } from 'lucide-react'

type Tab = 'profile' | 'analyze'

export default function ResumeManagerPage() {
  const [activeTab, setActiveTab] = useState<Tab>('profile')
  // Incrementing this causes the profile card to refetch after a new upload
  const [refetchSignal, setRefetchSignal] = useState(0)

  const handleAnalyzed = useCallback(() => {
    // After analysis completes we bump the refetch signal so the profile card
    // automatically re-fetches the latest stored resume data (upload may have
    // written a new Resume doc).
    setRefetchSignal(s => s + 1)
  }, [])

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'profile', label: 'Resume Profile', icon: <User className="w-4 h-4" /> },
    { id: 'analyze', label: 'Analyze vs. Job', icon: <Zap className="w-4 h-4" /> },
  ]

  return (
    <AppLayout>
      <div className="space-y-8">

        {/* ── Page header ────────────────────────────────────────────────── */}
        <div>
          <h1 className="text-3xl font-bold mb-2">Resume Manager</h1>
          <p className="text-muted-foreground">
            Upload once — get a structured AI profile, then match against any job description.
          </p>
        </div>

        {/* ── Tab switcher ───────────────────────────────────────────────── */}
        <div className="flex gap-1 p-1 bg-black/30 rounded-xl w-fit border border-white/5">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 ${
                activeTab === tab.id
                  ? 'bg-primary text-white shadow-md shadow-primary/30 scale-[1.02]'
                  : 'text-muted-foreground hover:text-white hover:bg-white/5'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* ── Tab content ────────────────────────────────────────────────── */}
        {activeTab === 'profile' && (
          <div className="animate-in slide-in-from-left-4 fade-in duration-300">
            <ResumeProfileCard refetchSignal={refetchSignal} />
          </div>
        )}

        {activeTab === 'analyze' && (
          <div className="animate-in slide-in-from-right-4 fade-in duration-300">
            {/* Pass callbacks so profile refetches after upload/analyze */}
            <ResumeAnalyzer onAnalyze={handleAnalyzed} onUpload={handleAnalyzed} />
          </div>
        )}

      </div>
    </AppLayout>
  )
}
