'use client'

import { useState, useRef } from 'react'
import { Upload, FileText, Loader2, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { uploadResume } from '@/src/services/api'
import { useAuth } from '@/context/auth-context'

export function ResumeUpload() {
    const { user } = useAuth()
    const [uploading, setUploading] = useState(false)
    const [isDragging, setIsDragging] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const handleFileSelect = async (file: File) => {
        if (file.size > 5 * 1024 * 1024) {
            toast.error('File size must be less than 5MB')
            return
        }

        setUploading(true)
        try {
            await uploadResume(file)
            toast.success('Resume uploaded successfully!')
            // Force reload to update user context / state
            window.location.reload()
        } catch (error) {
            toast.error('Failed to upload resume')
            console.error(error)
        } finally {
            setUploading(false)
        }
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
        const files = e.dataTransfer.files
        if (files && files.length > 0) {
            handleFileSelect(files[0])
        }
    }

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.currentTarget.files
        if (files && files.length > 0) {
            handleFileSelect(files[0])
        }
    }

    const hasResume = !!user?.resume_text

    return (
        <div className="glass rounded-xl p-6 glow flex flex-col justify-center">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                    {hasResume ? <CheckCircle2 className="w-5 h-5 text-green-400" /> : <Upload className="w-5 h-5 text-accent" />}
                    {hasResume ? 'Resume Active' : 'Upload Resume'}
                </h3>
            </div>

            <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => !uploading && fileInputRef.current?.click()}
                className={`w-full border-2 border-dashed rounded-lg flex flex-col items-center justify-center p-6 text-center transition-all ${uploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                    } ${isDragging
                        ? 'border-primary/50 bg-primary/10'
                        : hasResume ? 'border-green-500/30 bg-green-500/5 hover:border-green-500/50' : 'border-white/10 hover:border-white/20 hover:bg-white/5'
                    }`}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.doc,.docx"
                    onChange={handleFileInput}
                    className="hidden"
                    disabled={uploading}
                />

                {uploading ? (
                    <Loader2 className="w-8 h-8 animate-spin text-primary mb-2" />
                ) : hasResume ? (
                    <FileText className="w-8 h-8 text-green-400 mb-2" />
                ) : (
                    <Upload className="w-8 h-8 text-muted-foreground mb-2" />
                )}

                <p className="text-sm font-medium">
                    {uploading ? 'Uploading...' : hasResume ? 'Click or drag to Replace Resume' : 'Drag & drop or click to upload'}
                </p>
                <p className="text-xs text-muted-foreground mt-1">PDF, DOC, DOCX (Max 5MB)</p>
            </div>
        </div>
    )
}
