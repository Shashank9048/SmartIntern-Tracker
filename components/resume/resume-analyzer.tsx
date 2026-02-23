'use client'

import React, { useState, useRef, useEffect, useCallback } from "react"
import { Button } from '@/components/ui/button'
import { Upload, Zap, Save, CheckCircle2, XCircle, AlertCircle, FileText, ChevronDown } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/context/auth-context'
import { uploadResume, analyzeResume, updateUserProfile } from '@/src/services/api'
import { Skeleton } from "@/components/ui/skeleton"

interface ResumeAnalyzerProps {
  onAnalyze?: () => void
}

export function ResumeAnalyzer({ onAnalyze }: ResumeAnalyzerProps) {
  const { user, refreshUser } = useAuth()

  const [resumeText, setResumeText] = useState('')
  const [jobDescription, setJobDescription] = useState('')

  const [analyzing, setAnalyzing] = useState(false)
  const [isDragging, setIsDragging] = useState(false)

  const [isEditing, setIsEditing] = useState(false)
  const [savingResume, setSavingResume] = useState(false)

  const [analysisResult, setAnalysisResult] = useState<any>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Load saved resume on mount
  useEffect(() => {
    if (user?.resume_text && !resumeText && !isEditing) {
      setResumeText(user.resume_text)
    }
  }, [user, resumeText, isEditing])

  // Debounced auto-save
  useEffect(() => {
    if (!isEditing || !resumeText || resumeText === user?.resume_text) return;

    const timeoutId = setTimeout(async () => {
      setSavingResume(true);
      try {
        await updateUserProfile({ resume_text: resumeText });
        await refreshUser();
        toast.success("Resume auto-saved to profile")
      } catch (error) {
        console.error("Failed to auto-save resume:", error);
      } finally {
        setSavingResume(false);
      }
    }, 1500);

    return () => clearTimeout(timeoutId);
  }, [resumeText, isEditing, user, refreshUser])

  const handleFileSelect = async (file: File) => {
    if (file.size > 5 * 1024 * 1024) {
      toast.error('File size must be less than 5MB')
      return
    }

    const validTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
    if (!validTypes.includes(file.type)) {
      toast.error('Only PDF, DOC, or DOCX files are allowed')
      return
    }

    try {
      const toastId = toast.loading('Uploading and parsing resume...')
      // uploadResume returns { message, text_preview, uploaded_file_url }
      const result = await uploadResume(file)
      const extractedText = result?.text_preview || result?.resume_text || ''
      setResumeText(extractedText)
      await refreshUser() // sync user context (resume_text is also saved server-side)
      toast.dismiss(toastId)
      if (extractedText) {
        toast.success('Resume uploaded & parsed successfully!')
      } else {
        toast.warning('Resume uploaded but text could not be extracted. Try pasting text manually.')
      }
    } catch (error) {
      toast.error('Failed to upload/parse file')
      console.error('Upload error:', error)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleFileSelect(files[0])
    }
  }

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files
    if (files && files.length > 0) {
      handleFileSelect(files[0])
    }
  }

  const handleAnalyze = async () => {
    if (!resumeText || !jobDescription) return;
    setAnalyzing(true)
    setAnalysisResult(null)
    try {
      const result = await analyzeResume({ jobDescription, resumeText })
      setAnalysisResult(result)
      toast.success("Analysis Complete!")
      if (onAnalyze) onAnalyze()
    } catch (e: any) {
      // Check if it's a validation error (422) we mapped out in api-client
      if (e.message && e.message.includes('Validation Error')) {
        toast.error(e.message) // Show specific field errors
      } else {
        toast.error("Analysis Failed: Please check your input and try again.")
      }
    } finally {
      setAnalyzing(false)
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-500'
    if (score >= 50) return 'text-yellow-500'
    return 'text-red-500'
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'High': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'Medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      case 'Low': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }
  }

  return (
    <div className="space-y-6">

      {/* 1. Permanent Resume Upload Box */}
      <div className="glass rounded-xl p-6 glow">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Upload className="w-5 h-5" /> Upload Resume
        </h3>
        <div className="flex flex-col md:flex-row gap-6 items-center">

          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`flex-1 w-full border-2 border-dashed rounded-lg flex flex-col items-center justify-center p-6 text-center cursor-pointer transition-all ${isDragging
              ? 'border-primary/50 bg-primary/10'
              : 'border-white/10 hover:border-white/20 hover:bg-white/5'
              }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={handleFileInput}
              className="hidden"
            />
            <Upload className="w-8 h-8 mb-2 text-muted-foreground" />
            <p className="text-sm font-medium">Drag & drop or click to upload</p>
            <p className="text-xs text-muted-foreground mt-1">PDF, DOC, DOCX (Max 5MB)</p>
          </div>

          {(user?.resume_text || resumeText) && (
            <div className="flex-1 w-full p-6 bg-white/5 rounded-lg border border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <FileText className="w-10 h-10 text-primary" />
                <div>
                  <p className="text-sm font-semibold">
                    {/* Extract filename from URL or default */}
                    {(user as any)?.uploaded_file_url
                      ? (user as any).uploaded_file_url.split('/').pop()
                      : "resume_document.txt"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Saved to profile
                  </p>
                  {(user as any)?.uploaded_file_url && (
                    <a href={(user as any).uploaded_file_url} target="_blank" rel="noreferrer" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                      View Original File
                    </a>
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                  Replace
                </Button>
                <Button variant="destructive" size="sm" onClick={() => {
                  setResumeText('');
                  updateUserProfile({ resume_text: "" }).then(() => refreshUser());
                }}>
                  Delete
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 2. Resume Content PreviewSidebar */}
        <div className="glass rounded-xl p-6 glow flex flex-col h-[600px]">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <FileText className="w-5 h-5" /> Resume Preview
            </h3>
            <div className="flex items-center gap-3">
              {user?.resume_text && resumeText === user.resume_text && !isEditing && (
                <span className="text-xs px-2 py-1 bg-green-500/10 text-green-400 rounded-full border border-green-500/20 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Saved
                </span>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsEditing(!isEditing)}
                className="h-8 text-xs"
              >
                {isEditing ? 'Done Editing' : 'Edit Text'}
              </Button>
            </div>
          </div>

          <div className="flex-1 flex flex-col relative h-full min-h-[300px] overflow-hidden">
            {isEditing ? (
              <textarea
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
                placeholder="Your resume text will appear here..."
                spellCheck="false"
                className="w-full h-full rounded-lg p-5 font-mono text-sm leading-relaxed overflow-y-auto resize-none transition-colors border bg-black/50 border-primary/50 text-white focus:outline-none focus:ring-1 focus:ring-primary/50 whitespace-pre-wrap"
              />
            ) : (
              <div className="w-full h-full rounded-lg p-5 font-mono text-sm leading-relaxed overflow-y-auto border bg-white/5 border-white/10 text-gray-200 cursor-default whitespace-pre-wrap">
                {resumeText || "Your resume text will appear here..."}
              </div>
            )}
            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground px-1">
              <div>
                {resumeText.length} characters
              </div>
              {savingResume && (
                <div className="flex items-center gap-1 text-yellow-500">
                  <Zap className="w-3 h-3 animate-pulse" /> Saving...
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="glass rounded-xl p-6 glow flex flex-col h-[600px]">
          <h3 className="text-lg font-semibold mb-4">Target Job Description</h3>
          <textarea
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the target job description here to analyze match score..."
            spellCheck="false"
            className="w-full flex-1 min-h-[300px] bg-white/5 border border-white/10 rounded-lg p-5 text-sm text-white leading-relaxed focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 resize-none overflow-y-auto whitespace-pre-wrap"
          />
          <div className="mt-6 flex justify-end">
            <Button
              size="lg"
              onClick={handleAnalyze}
              disabled={analyzing || !resumeText || !jobDescription}
              className="w-full shadow-lg shadow-primary/20 transition-all hover:scale-[1.02] h-12 text-base"
            >
              {analyzing ? (
                <>
                  <Zap className="mr-2 h-5 w-5 animate-spin" />
                  Analyzing Document...
                </>
              ) : (
                <>
                  <div className="flex items-center justify-center w-full">
                    <Zap className="mr-2 h-5 w-5" />
                    Analyze Match
                  </div>
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Loading Skeletons */}
      {analyzing && (
        <div className="mt-8 space-y-6 animate-in fade-in duration-500">
          <div className="glass rounded-xl p-8 glow flex flex-col md:flex-row gap-8 items-center">
            <Skeleton className="w-32 h-32 rounded-full" />
            <div className="flex-1 space-y-4 w-full">
              <Skeleton className="h-8 w-1/3" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Skeleton className="h-48 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
            <Skeleton className="h-48 rounded-xl md:col-span-2" />
          </div>
        </div>
      )}

      {/* 4. Analysis Results View */}
      {analysisResult && !analyzing && (
        <div className="space-y-6 mt-8 animate-in slide-in-from-bottom-8 fade-in duration-700">

          {/* Main Score & Alignment Card */}
          <div className="glass rounded-xl p-8 glow relative overflow-hidden">
            {/* Background glow effect based on score */}
            <div className={`absolute top-0 right-0 w-64 h-64 bg-current opacity-5 blur-3xl rounded-full translate-x-1/2 -translate-y-1/2 ${getScoreColor(analysisResult.match_score)}`} />

            <div className="flex flex-col md:flex-row items-center gap-10">
              <div className="relative w-40 h-40 flex items-center justify-center shrink-0">
                <svg className="w-full h-full transform -rotate-90">
                  <circle
                    cx="80"
                    cy="80"
                    r="72"
                    stroke="currentColor"
                    strokeWidth="10"
                    fill="transparent"
                    className="text-white/5"
                  />
                  <circle
                    cx="80"
                    cy="80"
                    r="72"
                    stroke="currentColor"
                    strokeWidth="10"
                    fill="transparent"
                    strokeDasharray={452}
                    strokeDashoffset={452 - (452 * analysisResult.overall_match_score) / 100}
                    className={`transition-all duration-1500 ease-out ${getScoreColor(analysisResult.overall_match_score)}`}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className={`text-4xl font-extrabold ${getScoreColor(analysisResult.overall_match_score)}`}>
                    {analysisResult.overall_match_score}%
                  </span>
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mt-1">Match</span>
                </div>
              </div>

              <div className="flex-1 text-center md:text-left space-y-4">
                <div>
                  <h3 className="text-2xl font-bold text-white mb-2">Resume Compatibility</h3>
                  <p className="text-muted-foreground">Based on semantic analysis of your skills, experience, and the provided job description.</p>
                </div>

                <div className="flex flex-wrap gap-4 justify-center md:justify-start">
                  <div className="bg-black/30 px-4 py-3 rounded-xl border border-white/5">
                    <span className="block text-xs uppercase tracking-wider text-muted-foreground mb-1">ATS Score</span>
                    <span className="font-bold text-xl text-white">{analysisResult.ats_score || analysisResult.overall_match_score}%</span>
                  </div>
                  <div className="bg-black/30 px-4 py-3 rounded-xl border border-white/5">
                    <span className="block text-xs uppercase tracking-wider text-muted-foreground mb-1">Experience Alignment</span>
                    <span className={`font-bold text-xl ${analysisResult.experience_alignment === 'High' ? 'text-green-400' :
                      analysisResult.experience_alignment === 'Medium' ? 'text-yellow-400' : 'text-red-400'
                      }`}>{analysisResult.experience_alignment || "Medium"}</span>
                  </div>
                </div>

                {/* AI Summary block underneath */}
                {analysisResult.summary && (
                  <div className="mt-6 bg-black/20 p-5 rounded-xl border border-white/5">
                    <h4 className="flex items-center gap-2 font-bold mb-2">
                      <Zap className="w-4 h-4 text-primary" /> AI Match Summary
                    </h4>
                    <p className="text-sm text-gray-300 leading-relaxed italic">{analysisResult.summary}</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Matched Skills */}
            <div className="glass rounded-xl p-6 glow flex flex-col">
              <h4 className="font-bold text-lg mb-4 flex items-center border-b border-white/10 pb-3">
                <CheckCircle2 className="w-5 h-5 mr-3 text-green-500" /> Matched Skills
              </h4>
              <div className="flex flex-wrap gap-2 pt-2 flex-1 content-start">
                {analysisResult.skills_found && analysisResult.skills_found.length > 0 ? (
                  analysisResult.skills_found.map((skill: string, i: number) => (
                    <span key={i} className="px-3 py-1.5 bg-green-500/10 text-green-300 rounded-lg text-sm border border-green-500/20 font-medium">
                      {skill}
                    </span>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground italic w-full text-center py-4">No required skills clearly identified in resume.</p>
                )}
              </div>
            </div>

            {/* Missing Skills */}
            <div className="glass rounded-xl p-6 glow flex flex-col">
              <h4 className="font-bold text-lg mb-4 flex items-center border-b border-white/10 pb-3">
                <XCircle className="w-5 h-5 mr-3 text-red-500" /> Missing / Gap Skills
              </h4>
              <div className="flex flex-wrap gap-2 pt-2 flex-1 content-start">
                {analysisResult.missing_skills && analysisResult.missing_skills.length > 0 ? (
                  analysisResult.missing_skills.map((skill: string, i: number) => (
                    <span key={i} className="px-3 py-1.5 bg-red-500/10 text-red-300 rounded-lg text-sm border border-red-500/20 font-medium">
                      {skill}
                    </span>
                  ))
                ) : (
                  <p className="text-sm text-green-400 font-medium italic w-full text-center py-4 flex items-center justify-center gap-2">
                    <Zap className="w-4 h-4" /> Outstanding! No major missing skills detected.
                  </p>
                )}
              </div>
            </div>

            {/* Strengths */}
            {analysisResult.strengths && analysisResult.strengths.length > 0 && (
              <div className="glass rounded-xl p-6 glow">
                <h4 className="font-bold text-lg mb-4 text-white">Top Strengths</h4>
                <ul className="space-y-3">
                  {analysisResult.strengths.map((str: string, i: number) => (
                    <li key={i} className="flex gap-3 text-sm text-muted-foreground items-start">
                      <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{str}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Weaknesses */}
            {analysisResult.weaknesses && analysisResult.weaknesses.length > 0 && (
              <div className="glass rounded-xl p-6 glow">
                <h4 className="font-bold text-lg mb-4 text-white">Areas to Improve</h4>
                <ul className="space-y-3">
                  {analysisResult.weaknesses.map((weak: string, i: number) => (
                    <li key={i} className="flex gap-3 text-sm text-muted-foreground items-start">
                      <AlertCircle className="w-4 h-4 text-yellow-500 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{weak}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Improvement Suggestions */}
          {analysisResult.improvement_suggestions && analysisResult.improvement_suggestions.length > 0 && (
            <div className="glass rounded-xl p-0 glow overflow-hidden">
              <div className="p-6 border-b border-white/5 bg-white/[0.02]">
                <h3 className="text-xl font-bold flex items-center gap-3">
                  <Zap className="w-6 h-6 text-primary" /> Actionable Next Steps
                </h3>
                <p className="text-sm text-muted-foreground mt-2">Targeted recommendations to increase your chances for this role.</p>
              </div>
              <div className="p-6 space-y-4">
                {analysisResult.improvement_suggestions.map((suggestion: string, i: number) => (
                  <div key={i} className="flex flex-col md:flex-row items-start gap-4 p-5 rounded-xl bg-black/20 border border-white/5 hover:bg-white/5 transition-colors">
                    <div className="shrink-0 mt-0.5">
                      <Zap className="w-5 h-5 text-yellow-500" />
                    </div>
                    <div>
                      <p className="text-sm text-gray-200 leading-relaxed">{suggestion}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Resume Completeness Checklist */}
          {analysisResult.resume_completeness && (
            <div className="glass rounded-xl p-6 glow">
              <h4 className="font-bold text-lg mb-4">Structure Completeness</h4>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {Object.entries(analysisResult.resume_completeness).map(([key, value]) => (
                  <div key={key} className="flex flex-col gap-2 items-center text-center p-3 rounded-lg bg-black/20 border border-white/5">
                    {value ? (
                      <CheckCircle2 className="w-6 h-6 text-green-500" />
                    ) : (
                      <XCircle className="w-6 h-6 text-red-500" />
                    )}
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      {key.replace('has_', '').replace('_', ' ')}
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
