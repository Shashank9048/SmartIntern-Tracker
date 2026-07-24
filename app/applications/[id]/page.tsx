'use client'

import React, { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { AppLayout } from '@/components/app-layout'
import { APIClient } from '@/lib/api-client'
import { Application } from '@/types'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft, CheckCircle2, XCircle, AlertCircle, Zap, Calendar, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'

export default function ApplicationDetailsPage() {
    const params = useParams()
    const router = useRouter()
    const id = params?.id as string

    const [application, setApplication] = useState<Application | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!id) return;
        const fetchApplication = async () => {
            try {
                setLoading(true)
                const data = await APIClient.get<Application>(`/api/applications/${id}`)
                setApplication(data)
            } catch (err) {
                setError('Failed to load application details')
                toast.error('Failed to load application details')
            } finally {
                setLoading(false)
            }
        }
        fetchApplication()
    }, [id])

    const handleFollowUp = async () => {
        if (!application) return;
        try {
            await APIClient.post('/api/followup', { applicationId: application._id, type: 'Follow-up' })
            toast.success('Follow-up reminder created')
            router.push(`/cold-email?company=${encodeURIComponent(application.company_name)}&role=${encodeURIComponent(application.role)}`)
        } catch {
            toast.error('Failed to create reminder')
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

    if (loading) {
        return (
            <AppLayout>
                <div className="space-y-6 animate-in fade-in">
                    <Skeleton className="h-8 w-32 mb-8" />
                    <div className="glass rounded-xl p-8">
                        <Skeleton className="h-10 w-2/3 mb-4" />
                        <Skeleton className="h-4 w-1/3 mb-8" />
                        <Skeleton className="h-48 w-full" />
                    </div>
                </div>
            </AppLayout>
        )
    }

    if (error || !application) {
        return (
            <AppLayout>
                <div className="text-center py-20">
                    <h2 className="text-2xl font-bold mb-4">Application Not Found</h2>
                    <Button onClick={() => router.push('/applications')}>Back to Applications</Button>
                </div>
            </AppLayout>
        )
    }

    const analysis = application.analysis || (application.ai_match_score !== undefined ? {
        match_score: application.ai_match_score,
        experience_alignment: application.ai_experience_alignment,
        summary: application.ai_summary,
        missing_skills: application.ai_missing_skills,
        improvement_suggestions: application.ai_suggestions,
    } : undefined)

    const matchScore = analysis?.match_score ?? analysis?.overall_match_score ?? application.ai_match_score ?? 0

    return (
        <AppLayout>
            <div className="space-y-6">
                <Button variant="ghost" onClick={() => router.push('/applications')} className="mb-2 -ml-4 hover:bg-white/5">
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Back to Applications
                </Button>

                {/* Header Section */}
                <div className="glass rounded-xl p-8 glow relative overflow-hidden">
                    <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 relative z-10">
                        <div>
                            <div className="flex items-center gap-3 mb-2">
                                <h1 className="text-3xl font-bold">{application.company_name}</h1>
                                <Badge className={
                                    application.status === 'Selected' ? 'bg-green-500/20 text-green-400' :
                                        application.status === 'Rejected' ? 'bg-red-500/20 text-red-400' :
                                            application.status === 'Interview' ? 'bg-yellow-500/20 text-yellow-400' :
                                                'bg-blue-500/20 text-blue-400'
                                }>{application.status}</Badge>
                            </div>
                            <p className="text-xl text-muted-foreground">{application.role}</p>

                            <div className="flex flex-wrap gap-4 mt-6 text-sm text-muted-foreground">
                                <div className="flex items-center gap-1.5 border border-white/10 bg-white/5 px-3 py-1.5 rounded-lg">
                                    <Calendar className="w-4 h-4 text-primary" />
                                    Applied: {new Date(application.applied_date).toLocaleDateString()}
                                </div>
                                {application.interview_date && (
                                    <div className="flex items-center gap-1.5 border border-white/10 bg-yellow-500/10 px-3 py-1.5 rounded-lg">
                                        <Calendar className="w-4 h-4 text-yellow-500" />
                                        Interview: {new Date(application.interview_date).toLocaleDateString()}
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="flex flex-col gap-3 min-w-[200px]">
                            <Button onClick={handleFollowUp} className="w-full bg-gradient-to-r from-primary to-accent hover:opacity-90">
                                <ExternalLink className="w-4 h-4 mr-2" />
                                Follow Up / Cold Email
                            </Button>
                        </div>
                    </div>
                </div>

                {/* Analysis Section */}
                {analysis ? (
                    <div className="space-y-6 animate-in slide-in-from-bottom-8 duration-700">
                        {/* Compatibility Score Header */}
                        <div className="glass rounded-xl p-8 glow relative overflow-hidden">
                            <div className={`absolute top-0 right-0 w-64 h-64 bg-current opacity-5 blur-3xl rounded-full translate-x-1/2 -translate-y-1/2 ${getScoreColor(matchScore)}`} />

                            <div className="flex flex-col md:flex-row items-center gap-10 relative z-10">
                                <div className="relative w-40 h-40 flex items-center justify-center shrink-0">
                                    <svg className="w-full h-full transform -rotate-90">
                                        <circle cx="80" cy="80" r="72" stroke="currentColor" strokeWidth="10" fill="transparent" className="text-white/5" />
                                        <circle cx="80" cy="80" r="72" stroke="currentColor" strokeWidth="10" fill="transparent" strokeDasharray={452} strokeDashoffset={452 - (452 * matchScore) / 100} className={`transition-all duration-1500 ease-out ${getScoreColor(matchScore)}`} strokeLinecap="round" />
                                    </svg>
                                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                                        <span className={`text-4xl font-extrabold ${getScoreColor(matchScore)}`}>{matchScore}%</span>
                                        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mt-1">Match</span>
                                    </div>
                                </div>

                                <div className="flex-1 text-center md:text-left space-y-4">
                                    <div>
                                        <h3 className="text-2xl font-bold text-white mb-2">Job Compatibility</h3>
                                        <p className="text-muted-foreground">This score is specifically calculated for the <strong>{application.role}</strong> role based on the resume snapshot you applied with.</p>
                                    </div>

                                    <div className="flex flex-wrap gap-4 justify-center md:justify-start">
                                        {analysis.ats_score !== undefined && (
                                            <div className="bg-black/30 px-4 py-3 rounded-xl border border-white/5">
                                                <span className="block text-xs uppercase tracking-wider text-muted-foreground mb-1">ATS Score</span>
                                                <span className="font-bold text-xl text-white">{analysis.ats_score}%</span>
                                            </div>
                                        )}
                                        {analysis.experience_alignment && (
                                            <div className="bg-black/30 px-4 py-3 rounded-xl border border-white/5">
                                                <span className="block text-xs uppercase tracking-wider text-muted-foreground mb-1">Experience Alignment</span>
                                                <span className={`font-bold text-xl ${analysis.experience_alignment === 'High' ? 'text-green-400' : analysis.experience_alignment === 'Medium' ? 'text-yellow-400' : 'text-red-400'}`}>{analysis.experience_alignment}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Matched Skills */}
                            <div className="glass rounded-xl p-6 glow flex flex-col">
                                <h4 className="font-bold text-lg mb-4 flex items-center border-b border-white/10 pb-3">
                                    <CheckCircle2 className="w-5 h-5 mr-3 text-green-500" /> Skills Matched
                                </h4>
                                <div className="flex flex-wrap gap-2 pt-2 flex-1 content-start">
                                    {analysis.skills_found?.length ? analysis.skills_found.map((skill: string, i: number) => (
                                        <span key={i} className="px-3 py-1.5 bg-green-500/10 text-green-300 rounded-lg text-sm border border-green-500/20 font-medium">{skill}</span>
                                    )) : <p className="text-sm text-muted-foreground italic w-full text-center py-4">No specific matching skills clearly identified.</p>}
                                </div>
                            </div>

                            {/* Missing Skills */}
                            <div className="glass rounded-xl p-6 glow flex flex-col">
                                <h4 className="font-bold text-lg mb-4 flex items-center border-b border-white/10 pb-3">
                                    <XCircle className="w-5 h-5 mr-3 text-red-500" /> Missing / Gap Skills
                                </h4>
                                <div className="flex flex-wrap gap-2 pt-2 flex-1 content-start">
                                    {analysis.missing_skills?.length ? analysis.missing_skills.map((skill: string, i: number) => (
                                        <span key={i} className="px-3 py-1.5 bg-red-500/10 text-red-300 rounded-lg text-sm border border-red-500/20 font-medium">{skill}</span>
                                    )) : <p className="text-sm text-green-400 font-medium italic w-full text-center py-4 flex items-center justify-center gap-2"><Zap className="w-4 h-4" /> Outstanding! No major missing skills detected.</p>}
                                </div>
                            </div>

                            {/* Strengths */}
                            {analysis.strengths && analysis.strengths.length > 0 && (
                                <div className="glass rounded-xl p-6 glow">
                                    <h4 className="font-bold text-lg mb-4 text-white flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-primary" /> Top Strengths</h4>
                                    <ul className="space-y-3">
                                        {analysis.strengths.map((str: string, i: number) => (
                                            <li key={i} className="flex gap-3 text-sm text-muted-foreground items-start">
                                                <div className="w-1.5 h-1.5 rounded-full bg-primary shrink-0 mt-2" />
                                                <span className="leading-relaxed">{str}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Weaknesses */}
                            {analysis.weaknesses && analysis.weaknesses.length > 0 && (
                                <div className="glass rounded-xl p-6 glow">
                                    <h4 className="font-bold text-lg mb-4 text-white flex items-center gap-2"><AlertCircle className="w-5 h-5 text-yellow-500" /> Areas to Improve</h4>
                                    <ul className="space-y-3">
                                        {analysis.weaknesses.map((weak: string, i: number) => (
                                            <li key={i} className="flex gap-3 text-sm text-muted-foreground items-start">
                                                <div className="w-1.5 h-1.5 rounded-full bg-yellow-500 shrink-0 mt-2" />
                                                <span className="leading-relaxed">{weak}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>

                        {/* Action Plan */}
                        {analysis.action_plan && analysis.action_plan.length > 0 && (
                            <div className="glass rounded-xl p-0 glow overflow-hidden">
                                <div className="p-6 border-b border-white/5 bg-white/[0.02]">
                                    <h3 className="text-xl font-bold flex items-center gap-3">
                                        <Zap className="w-6 h-6 text-primary" /> Actionable Next Steps
                                    </h3>
                                    <p className="text-sm text-muted-foreground mt-2">Targeted recommendations to improve your candidacy if you get an interview, or for future applications to similar roles.</p>
                                </div>
                                <div className="p-6 space-y-4">
                                    {analysis.action_plan.map((item: any, i: number) => (
                                        <div key={i} className="flex flex-col md:flex-row items-start gap-4 p-5 rounded-xl bg-black/20 border border-white/5 hover:bg-white/5 transition-colors">
                                            <div className={`shrink-0 px-3 py-1 rounded border text-xs font-bold uppercase tracking-wider ${getPriorityColor(item.priority)}`}>
                                                {item.priority} Priority
                                            </div>
                                            <div>
                                                <h5 className="text-base font-bold text-white mb-1.5">{item.title}</h5>
                                                <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Job Description & Resume Snapshot View */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div className="glass rounded-xl p-6 glow flex flex-col h-[500px]">
                                <h3 className="text-lg font-bold mb-4">Job Description Context</h3>
                                <div className="w-full flex-1 bg-black/30 border border-white/10 rounded-lg p-5 text-sm text-gray-300 leading-relaxed overflow-y-auto whitespace-pre-wrap font-mono">
                                    {analysis.job_description || "No job description provided."}
                                </div>
                            </div>
                            <div className="glass rounded-xl p-6 glow flex flex-col h-[500px]">
                                <h3 className="text-lg font-bold mb-4">Resume Snapshot</h3>
                                <div className="w-full flex-1 bg-black/30 border border-white/10 rounded-lg p-5 text-sm text-gray-300 leading-relaxed overflow-y-auto whitespace-pre-wrap font-mono">
                                    {analysis.resume_snapshot || "No resume snapshot found."}
                                </div>
                            </div>
                        </div>

                    </div>
                ) : (
                    <div className="glass rounded-xl p-12 text-center">
                        <h3 className="text-xl font-bold mb-2">No Detailed Analysis Found</h3>
                        <p className="text-muted-foreground">This application was created before the detailed job compatibility feature was implemented, or no resume was available at the time of creation.</p>
                    </div>
                )}
            </div>
        </AppLayout>
    )
}
