'use client'

import React, { useState, useRef, useEffect, useCallback } from "react"
import { Button } from '@/components/ui/button'
import {
  Upload, Zap, CheckCircle2, XCircle, AlertCircle,
  FileText, RefreshCw, Trash2, Eye, Edit3, BarChart2
} from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/context/auth-context'
import { uploadResume, analyzeResume, updateUserProfile, deleteResume } from '@/src/services/api'
import { Skeleton } from "@/components/ui/skeleton"

interface ResumeAnalyzerProps {
  onAnalyze?: () => void
  /** Called after a successful upload — lets parent refresh the profile card */
  onUpload?: () => void
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Lightweight smart formatter for resume text preview.
 * Detects section headers, bullet points, and regular lines.
 */
function ResumePreviewContent({ text }: { text: string }) {
  if (!text) return null

  const SECTION_KEYWORDS = new Set([
    'EDUCATION', 'EXPERIENCE', 'WORK EXPERIENCE', 'EMPLOYMENT HISTORY',
    'PROJECTS', 'SKILLS', 'TECHNICAL SKILLS', 'CORE SKILLS',
    'CERTIFICATIONS', 'SUMMARY', 'PROFESSIONAL SUMMARY', 'OBJECTIVE',
    'CAREER OBJECTIVE', 'ACHIEVEMENTS', 'AWARDS', 'LANGUAGES',
    'INTERNSHIP', 'INTERNSHIPS', 'VOLUNTEER', 'CONTACT', 'REFERENCES',
    'PUBLICATIONS', 'HOBBIES', 'INTERESTS', 'PROFILE',
  ])

  const lines = text.split('\n')

  return (
    <>
      {lines.map((line, idx) => {
        const trimmed = line.trim()
        if (!trimmed) return <div key={idx} className="h-2" />

        // Clean link artifacts like |Link or [Link]
        const cleanLine = trimmed
          .replace(/\|\s*Link\b/gi, ' ')
          .replace(/\[Link\]/gi, '')
          .replace(/\s{2,}/g, ' ')
          .trim()

        if (!cleanLine) return null

        const upper = cleanLine.toUpperCase().replace(/[:·|]/g, '').trim()

        const isSectionHeader =
          SECTION_KEYWORDS.has(upper) ||
          Array.from(SECTION_KEYWORDS).some(
            kw => upper === kw || upper.startsWith(kw + ' ') || upper.endsWith(' ' + kw)
          )

        if (isSectionHeader) {
          return (
            <div key={idx} className="mt-5 mb-2 flex items-center gap-3">
              <span className="text-xs font-bold uppercase tracking-widest text-primary whitespace-nowrap">
                {cleanLine}
              </span>
              <div className="flex-1 h-px bg-primary/20" />
            </div>
          )
        }

        if (/^[•\-\*>]\s/.test(cleanLine)) {
          return (
            <div key={idx} className="flex gap-2 text-sm text-gray-300 leading-relaxed pl-2 py-0.5">
              <span className="text-primary/60 mt-1 shrink-0 text-xs">▸</span>
              <span>{cleanLine.replace(/^[•\-\*>]\s*/, '')}</span>
            </div>
          )
        }

        // First few lines → likely name/header
        if (idx < 4 && cleanLine.length < 80) {
          return (
            <p key={idx} className="text-base font-semibold text-white leading-snug py-0.5">
              {cleanLine}
            </p>
          )
        }

        return (
          <p key={idx} className="text-sm text-gray-300 leading-relaxed py-0.5">
            {cleanLine}
          </p>
        )
      })}
    </>
  )
}

function getScoreColor(score: number) {
  if (score >= 80) return 'text-green-400'
  if (score >= 55) return 'text-yellow-400'
  return 'text-red-400'
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function ResumeAnalyzer({ onAnalyze, onUpload }: ResumeAnalyzerProps) {
  const { user, refreshUser } = useAuth()

  // Core state
  const [resumeText, setResumeText] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [uploadedFileName, setUploadedFileName] = useState<string>('')

  // UI state
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [savingResume, setSavingResume] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<any>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  // Track whether we've already loaded from user profile (avoid overriding user edits)
  const initializedRef = useRef(false)

  // ── Load saved resume from profile ONCE on mount ─────────────────────────
  useEffect(() => {
    if (initializedRef.current) return
    if (!user) return

    initializedRef.current = true

    if (user.resume_text) {
      setResumeText(user.resume_text)
    }
    const fileUrl = (user as any)?.uploaded_file_url
    if (fileUrl) {
      setUploadedFileName(fileUrl.split('/').pop() || 'resume')
    }
  }, [user])

  // ── Auto-save when user edits text manually ───────────────────────────────
  useEffect(() => {
    if (!isEditing || !resumeText || resumeText === user?.resume_text) return

    const id = setTimeout(async () => {
      setSavingResume(true)
      try {
        await updateUserProfile({ resume_text: resumeText })
        await refreshUser()
        toast.success('Resume auto-saved')
      } catch {
        // silent
      } finally {
        setSavingResume(false)
      }
    }, 1500)

    return () => clearTimeout(id)
  }, [resumeText, isEditing]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Upload handler ────────────────────────────────────────────────────────
  const handleFileSelect = useCallback(async (file: File) => {
    if (file.size > 5 * 1024 * 1024) {
      toast.error('File must be under 5 MB')
      return
    }
    if (!file.name.match(/\.(pdf|doc|docx)$/i)) {
      toast.error('Only PDF, DOC, or DOCX files are allowed')
      return
    }

    setUploading(true)
    const toastId = toast.loading(`Uploading ${file.name}…`)

    try {
      const result = await uploadResume(file)

      // Backend returns: { full_text, text_preview, uploaded_file_url, characters, filename }
      const extractedText: string =
        result?.full_text ??
        result?.resume_text ??
        result?.text_preview ??
        ''

      // Update preview immediately — don't wait for refreshUser
      setResumeText(extractedText)
      setUploadedFileName(file.name)
      setAnalysisResult(null)

      // Sync user context in background (don't block UI)
      refreshUser().catch(() => { })

      toast.dismiss(toastId)

      if (extractedText && extractedText.length > 50) {
        toast.success(
          `✓ Parsed ${(result?.characters ?? extractedText.length).toLocaleString()} characters from ${file.name}`
        )
        // Phase 2: notify parent to refresh the profile card
        onUpload?.()
      } else if (extractedText) {
        toast.warning('File uploaded. Limited text extracted — you can also paste text manually using Edit.')
      } else {
        toast.warning(
          'Could not extract text from this file. Please click Edit and paste your resume text manually.'
        )
      }
    } catch (err: any) {
      toast.dismiss(toastId)
      toast.error(err?.message || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }, [refreshUser])

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true) }
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(false) }
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFileSelect(file)
  }
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.currentTarget.files?.[0]
    if (file) handleFileSelect(file)
    // Reset so same file can be re-selected
    e.currentTarget.value = ''
  }

  const handleClear = async () => {
    setResumeText('')
    setUploadedFileName('')
    setAnalysisResult(null)
    setIsEditing(false)
    try {
      await deleteResume()
      await refreshUser()
      onUpload?.()
    } catch {
      try {
        await updateUserProfile({ resume_text: '' })
        await refreshUser()
      } catch {
        // silent — local state is already cleared
      }
    }
    toast.info('Resume cleared')
  }

  const handleReplace = () => {
    fileInputRef.current?.click()
  }

  // ── Analyze ───────────────────────────────────────────────────────────────
  const handleAnalyze = async () => {
    if (!resumeText.trim()) {
      toast.error('Upload or paste your resume first')
      return
    }
    if (!jobDescription.trim()) {
      toast.error('Paste a job description first')
      return
    }

    setAnalyzing(true)
    setAnalysisResult(null)

    try {
      const result = await analyzeResume({ jobDescription, resumeText })
      setAnalysisResult(result)
      toast.success('Analysis complete!')
      onAnalyze?.()
    } catch (e: any) {
      toast.error(e?.message || 'Analysis failed. Please try again.')
    } finally {
      setAnalyzing(false)
    }
  }

  // ── Computed ──────────────────────────────────────────────────────────────
  const wordCount = resumeText.trim() ? resumeText.trim().split(/\s+/).length : 0
  const hasResume = resumeText.length > 0 || uploadedFileName.length > 0

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* ── 1. Upload Zone ─────────────────────────────────────────────── */}
      <div className="glass rounded-xl p-6 glow">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Upload className="w-5 h-5 text-primary" /> Upload Resume
        </h3>

        <div className="flex flex-col md:flex-row gap-4">

          {/* Drop zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
            className={`${hasResume ? 'md:w-52 shrink-0' : 'flex-1'} border-2 border-dashed rounded-xl flex flex-col items-center justify-center p-6 text-center cursor-pointer transition-all duration-200 min-h-[120px] ${isDragging
                ? 'border-primary bg-primary/15 scale-[1.01]'
                : uploading
                  ? 'border-primary/30 bg-primary/5 cursor-not-allowed opacity-70'
                  : 'border-white/10 hover:border-primary/40 hover:bg-white/5'
              }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={handleFileInput}
              className="hidden"
            />
            {uploading ? (
              <>
                <RefreshCw className="w-7 h-7 mb-2 text-primary animate-spin" />
                <p className="text-sm font-medium text-primary">Parsing…</p>
              </>
            ) : (
              <>
                <Upload className="w-7 h-7 mb-2 text-muted-foreground" />
                <p className="text-sm font-semibold">{hasResume ? 'Upload new' : 'Drag & Drop or Click'}</p>
                <p className="text-xs text-muted-foreground mt-1">PDF · DOC · DOCX · Max 5 MB</p>
              </>
            )}
          </div>

          {/* File info card — shown whenever resume is loaded */}
          {hasResume && (
            <div className="flex-1 bg-white/5 rounded-xl border border-white/10 p-5 flex items-center justify-between gap-4 min-w-0">
              <div className="flex items-center gap-4 min-w-0">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                  <FileText className="w-5 h-5 text-primary" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold truncate">
                    {uploadedFileName || 'resume_text.txt'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {wordCount.toLocaleString()} words · {resumeText.length.toLocaleString()} characters
                  </p>
                  {(user as any)?.uploaded_file_url && (
                    <a
                      href={`http://localhost:8000${(user as any).uploaded_file_url}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      View original ↗
                    </a>
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-2 shrink-0">
                <Button variant="outline" size="sm" onClick={handleReplace} disabled={uploading}>
                  <RefreshCw className="w-3 h-3 mr-1.5" /> Replace
                </Button>
                <Button variant="destructive" size="sm" onClick={handleClear} disabled={uploading}>
                  <Trash2 className="w-3 h-3 mr-1.5" /> Clear
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 2. Preview + Job Description ───────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Resume Preview */}
        <div className="glass rounded-xl p-6 glow flex flex-col h-[600px]">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Eye className="w-5 h-5 text-primary" /> Resume Preview
            </h3>
            <div className="flex items-center gap-2">
              {savingResume && (
                <span className="text-xs text-yellow-400 flex items-center gap-1 animate-pulse">
                  <Zap className="w-3 h-3" /> Saving…
                </span>
              )}
              {!savingResume && resumeText && (
                <span className="text-xs px-2 py-1 bg-green-500/10 text-green-400 rounded-full border border-green-500/20 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" />
                  {resumeText === user?.resume_text ? 'Saved' : 'Loaded'}
                </span>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsEditing(v => !v)}
                className="h-7 text-xs gap-1.5"
              >
                <Edit3 className="w-3 h-3" />
                {isEditing ? 'Preview' : 'Edit'}
              </Button>
            </div>
          </div>

          <div className="flex-1 relative overflow-hidden">
            {isEditing ? (
              <textarea
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
                placeholder="Paste your resume text here…"
                spellCheck={false}
                autoFocus
                className="w-full h-full rounded-lg p-4 font-mono text-xs leading-relaxed resize-none bg-black/40 border border-primary/40 text-white focus:outline-none focus:ring-1 focus:ring-primary/60 overflow-y-auto"
              />
            ) : resumeText ? (
              <div className="w-full h-full rounded-lg p-5 overflow-y-auto border bg-white/[0.03] border-white/10">
                <ResumePreviewContent text={resumeText} />
              </div>
            ) : (
              <div className="w-full h-full rounded-lg border border-dashed border-white/10 flex flex-col items-center justify-center gap-3 text-center p-8">
                <FileText className="w-10 h-10 text-muted-foreground/40" />
                <div>
                  <p className="text-sm text-muted-foreground">No resume loaded yet</p>
                  <p className="text-xs text-muted-foreground/60 mt-1">
                    Upload a file above, or{' '}
                    <button
                      onClick={() => setIsEditing(true)}
                      className="text-primary hover:underline"
                    >
                      click Edit to paste text
                    </button>
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground px-1">
            <span>{wordCount.toLocaleString()} words · {resumeText.length.toLocaleString()} chars</span>
          </div>
        </div>

        {/* Job Description */}
        <div className="glass rounded-xl p-6 glow flex flex-col h-[600px]">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-primary" /> Target Job Description
          </h3>
          <textarea
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the full job description here to get your match score, skill gaps, and improvement tips…"
            spellCheck={false}
            className="w-full flex-1 min-h-0 bg-white/5 border border-white/10 rounded-lg p-5 text-sm text-white leading-relaxed focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 resize-none overflow-y-auto"
          />
          <div className="mt-4">
            <Button
              size="lg"
              onClick={handleAnalyze}
              disabled={analyzing || uploading || !resumeText.trim() || !jobDescription.trim()}
              className="w-full h-12 text-base shadow-lg shadow-primary/20 transition-all hover:scale-[1.01] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {analyzing ? (
                <><RefreshCw className="mr-2 h-5 w-5 animate-spin" /> Analyzing with AI…</>
              ) : (
                <><Zap className="mr-2 h-5 w-5" /> Analyze Match</>
              )}
            </Button>
            {!resumeText.trim() && (
              <p className="text-xs text-muted-foreground text-center mt-2">
                ↑ Upload or paste your resume to enable analysis
              </p>
            )}
            {resumeText.trim() && !jobDescription.trim() && (
              <p className="text-xs text-muted-foreground text-center mt-2">
                ↑ Paste a job description to enable analysis
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ── 3. Loading skeleton ─────────────────────────────────────────── */}
      {analyzing && (
        <div className="space-y-6 animate-in fade-in duration-500">
          <div className="glass rounded-xl p-8 glow flex flex-col md:flex-row gap-8 items-center">
            <Skeleton className="w-36 h-36 rounded-full shrink-0" />
            <div className="flex-1 space-y-3 w-full">
              <Skeleton className="h-7 w-1/3" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-4/6" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Skeleton className="h-44 rounded-xl" />
            <Skeleton className="h-44 rounded-xl" />
            <Skeleton className="h-44 rounded-xl md:col-span-2" />
          </div>
        </div>
      )}

      {/* ── 4. Analysis Results ─────────────────────────────────────────── */}
      {analysisResult && !analyzing && (
        <div className="space-y-6 animate-in slide-in-from-bottom-6 fade-in duration-700">

          {/* Score card */}
          <div className="glass rounded-xl p-8 glow relative overflow-hidden">
            <div className={`absolute top-0 right-0 w-72 h-72 opacity-5 blur-3xl rounded-full translate-x-1/2 -translate-y-1/2 bg-current ${getScoreColor(analysisResult.overall_match_score)}`} />
            <div className="flex flex-col md:flex-row items-center gap-10">
              {/* Circular score */}
              <div className="relative w-40 h-40 flex items-center justify-center shrink-0">
                <svg className="w-full h-full -rotate-90">
                  <circle cx="80" cy="80" r="68" stroke="currentColor" strokeWidth="10"
                    fill="transparent" className="text-white/5" />
                  <circle cx="80" cy="80" r="68" stroke="currentColor" strokeWidth="10"
                    fill="transparent"
                    strokeDasharray={427}
                    strokeDashoffset={427 - (427 * (analysisResult.overall_match_score || 0)) / 100}
                    className={`transition-all duration-[1500ms] ease-out ${getScoreColor(analysisResult.overall_match_score)}`}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className={`text-4xl font-extrabold ${getScoreColor(analysisResult.overall_match_score)}`}>
                    {analysisResult.overall_match_score ?? 0}%
                  </span>
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mt-1">Match</span>
                </div>
              </div>

              <div className="flex-1 text-center md:text-left space-y-4">
                <div>
                  <h3 className="text-2xl font-bold text-white mb-1">Resume Compatibility</h3>
                  <p className="text-sm text-muted-foreground">AI-powered semantic analysis of your skills vs. the job description.</p>
                </div>
                <div className="flex flex-wrap gap-3 justify-center md:justify-start">
                  <div className="bg-black/30 px-4 py-3 rounded-xl border border-white/5 text-center">
                    <span className="block text-xs uppercase tracking-wider text-muted-foreground mb-1">ATS Score</span>
                    <span className="font-bold text-xl text-white">{analysisResult.ats_score ?? analysisResult.overall_match_score ?? 0}%</span>
                  </div>
                  <div className="bg-black/30 px-4 py-3 rounded-xl border border-white/5 text-center">
                    <span className="block text-xs uppercase tracking-wider text-muted-foreground mb-1">Experience</span>
                    <span className={`font-bold text-xl ${analysisResult.experience_alignment === 'High' ? 'text-green-400' :
                        analysisResult.experience_alignment === 'Medium' ? 'text-yellow-400' : 'text-red-400'
                      }`}>{analysisResult.experience_alignment ?? 'Low'}</span>
                  </div>
                </div>
                {analysisResult.summary && (
                  <div className="bg-black/30 p-4 rounded-xl border border-white/5">
                    <h4 className="flex items-center gap-2 font-semibold mb-1.5 text-sm">
                      <Zap className="w-4 h-4 text-primary" /> AI Summary
                    </h4>
                    <p className="text-sm text-gray-300 leading-relaxed italic">{analysisResult.summary}</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Skills */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass rounded-xl p-6 glow">
              <h4 className="font-bold mb-4 flex items-center gap-2 border-b border-white/10 pb-3">
                <CheckCircle2 className="w-4 h-4 text-green-500" /> Matched Skills
              </h4>
              <div className="flex flex-wrap gap-2">
                {analysisResult.skills_found?.length > 0
                  ? analysisResult.skills_found.map((s: string, i: number) => (
                    <span key={i} className="px-3 py-1.5 bg-green-500/10 text-green-300 rounded-lg text-sm border border-green-500/20 font-medium">{s}</span>
                  ))
                  : <p className="text-sm text-muted-foreground italic py-4 w-full text-center">No matched skills found</p>
                }
              </div>
            </div>
            <div className="glass rounded-xl p-6 glow">
              <h4 className="font-bold mb-4 flex items-center gap-2 border-b border-white/10 pb-3">
                <XCircle className="w-4 h-4 text-red-500" /> Missing Skills
              </h4>
              <div className="flex flex-wrap gap-2">
                {analysisResult.missing_skills?.length > 0
                  ? analysisResult.missing_skills.map((s: string, i: number) => (
                    <span key={i} className="px-3 py-1.5 bg-red-500/10 text-red-300 rounded-lg text-sm border border-red-500/20 font-medium">{s}</span>
                  ))
                  : <p className="text-sm text-green-400 font-medium italic w-full text-center py-4 flex items-center justify-center gap-2"><CheckCircle2 className="w-4 h-4" /> No major skill gaps!</p>
                }
              </div>
            </div>

            {analysisResult.strengths?.length > 0 && (
              <div className="glass rounded-xl p-6 glow">
                <h4 className="font-bold mb-4 text-white">Top Strengths</h4>
                <ul className="space-y-2">
                  {analysisResult.strengths.map((s: string, i: number) => (
                    <li key={i} className="flex gap-3 text-sm text-muted-foreground items-start">
                      <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {analysisResult.weaknesses?.length > 0 && (
              <div className="glass rounded-xl p-6 glow">
                <h4 className="font-bold mb-4 text-white">Areas to Improve</h4>
                <ul className="space-y-2">
                  {analysisResult.weaknesses.map((w: string, i: number) => (
                    <li key={i} className="flex gap-3 text-sm text-muted-foreground items-start">
                      <AlertCircle className="w-4 h-4 text-yellow-500 shrink-0 mt-0.5" />
                      <span>{w}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Improvement steps */}
          {analysisResult.improvement_suggestions?.length > 0 && (
            <div className="glass rounded-xl overflow-hidden glow">
              <div className="p-6 border-b border-white/5 bg-white/[0.02]">
                <h3 className="text-lg font-bold flex items-center gap-3">
                  <Zap className="w-5 h-5 text-primary" /> Actionable Next Steps
                </h3>
                <p className="text-sm text-muted-foreground mt-1">Targeted recommendations to improve your match for this specific role.</p>
              </div>
              <div className="p-6 space-y-3">
                {analysisResult.improvement_suggestions.map((tip: string, i: number) => (
                  <div key={i} className="flex items-start gap-4 p-4 rounded-xl bg-black/20 border border-white/5 hover:bg-white/[0.04] transition-colors">
                    <span className="w-6 h-6 rounded-full bg-primary/20 text-primary text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">{i + 1}</span>
                    <p className="text-sm text-gray-200 leading-relaxed">{tip}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Completeness */}
          {analysisResult.resume_completeness && (
            <div className="glass rounded-xl p-6 glow">
              <h4 className="font-bold mb-4">Resume Structure Check</h4>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {Object.entries(analysisResult.resume_completeness).map(([key, value]) => (
                  <div key={key} className="flex flex-col gap-2 items-center text-center p-4 rounded-xl bg-black/20 border border-white/5">
                    {value ? <CheckCircle2 className="w-6 h-6 text-green-500" /> : <XCircle className="w-6 h-6 text-red-400" />}
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      {key.replace('has_', '').replace(/_/g, ' ')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  )
}
