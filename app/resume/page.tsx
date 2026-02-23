'use client'

import { AppLayout } from '@/components/app-layout'
import { ResumeAnalyzer } from '@/components/resume/resume-analyzer'
export default function ResumeManagerPage() {
  return (
    <AppLayout>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold mb-2">Resume Manager</h1>
          <p className="text-muted-foreground">
            Analyze your resume against job descriptions
          </p>
        </div>

        {/* Analyzer */}
        <ResumeAnalyzer />

      </div>
    </AppLayout>
  )
}
