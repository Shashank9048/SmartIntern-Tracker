'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import Link from 'next/link'
import { Eye, EyeOff, X, Loader2, CheckCircle2 } from 'lucide-react'
import { useAuth } from '@/context/auth-context'
import { toast } from 'sonner'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function SignupPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [skillInput, setSkillInput] = useState('')
  const [skills, setSkills] = useState<string[]>([])
  const [branch, setBranch] = useState('')
  const [graduationYear, setGraduationYear] = useState('')
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const { refreshUser } = useAuth()
  const router = useRouter()

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!name.trim() || !email.trim() || !password || !confirmPassword) {
      toast.error('Please fill in all required fields')
      return
    }
    if (password !== confirmPassword) {
      toast.error('Passwords do not match')
      return
    }
    if (password.length < 6) {
      toast.error('Password must be at least 6 characters')
      return
    }

    setLoading(true)
    try {
      // 1. Signup
      const res = await fetch(`${API_URL}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim(),
          password,
          full_name: name.trim(),
          branch: branch || '',
          graduation_year: graduationYear || '',
          skills,
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        const msg = data?.detail || data?.message || `Error ${res.status}`
        throw new Error(msg)
      }

      if (!data.access_token) {
        throw new Error('No token received from server')
      }

      // Store token
      localStorage.setItem('access_token', data.access_token)
      document.cookie = `access_token=${data.access_token}; path=/; max-age=604800`

      // 2. Upload Resume if provided
      if (resumeFile) {
        try {
          const { uploadResume } = await import('@/src/services/api')
          await uploadResume(resumeFile)
          toast.success('Resume uploaded successfully!')
        } catch (uploadErr) {
          console.error('Resume upload failed:', uploadErr)
          toast.error('Account created, but resume upload failed. You can upload it later in settings.')
        }
      }

      // 3. Sync auth context
      await refreshUser()

      toast.success('Account created! Welcome aboard 🎉')
      router.push('/dashboard')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Signup failed. Please try again.'
      toast.error(msg)
      if (msg.toLowerCase().includes('already') || msg.toLowerCase().includes('registered')) {
        setTimeout(() => router.push(`/login?email=${encodeURIComponent(email)}`), 1800)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleAddSkill = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      const s = skillInput.trim()
      if (s && !skills.includes(s)) {
        setSkills([...skills, s])
        setSkillInput('')
      }
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 py-12">
      <div className="w-full max-w-2xl">
        <div className="glass rounded-2xl p-8 space-y-6 glow">
          {/* Header */}
          <div>
            <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary mb-2">
              SmartIntern
            </h1>
            <h2 className="text-2xl font-bold mb-1">Create Your Account</h2>
            <p className="text-muted-foreground text-sm">
              Start tracking your internship journey with AI-powered insights
            </p>
          </div>

          <form onSubmit={handleSignup} className="space-y-4">
            {/* Name + Email */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">Full Name <span className="text-red-400">*</span></label>
                <Input
                  type="text"
                  placeholder="Shashank Singh"
                  className="glass rounded-lg border-white/10"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Email Address <span className="text-red-400">*</span></label>
                <Input
                  type="email"
                  placeholder="you@example.com"
                  className="glass rounded-lg border-white/10"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>
            </div>

            {/* Passwords */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">Password <span className="text-red-400">*</span></label>
                <div className="relative">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Min. 6 characters"
                    className="glass rounded-lg border-white/10 pr-10"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                    required
                  />
                  <button type="button" onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Confirm Password <span className="text-red-400">*</span></label>
                <div className="relative">
                  <Input
                    type={showConfirmPassword ? 'text' : 'password'}
                    placeholder="Re-enter password"
                    className="glass rounded-lg border-white/10 pr-10"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    disabled={loading}
                    required
                  />
                  <button type="button" onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>

            {/* Branch + Year */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">Branch</label>
                <Select value={branch} onValueChange={setBranch} disabled={loading}>
                  <SelectTrigger className="glass border-white/10 rounded-lg">
                    <SelectValue placeholder="Select branch (optional)" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-white/10">
                    <SelectItem value="cse">Computer Science</SelectItem>
                    <SelectItem value="ece">Electronics & Communication</SelectItem>
                    <SelectItem value="me">Mechanical Engineering</SelectItem>
                    <SelectItem value="ce">Civil Engineering</SelectItem>
                    <SelectItem value="it">Information Technology</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Graduation Year</label>
                <Select value={graduationYear} onValueChange={setGraduationYear} disabled={loading}>
                  <SelectTrigger className="glass border-white/10 rounded-lg">
                    <SelectValue placeholder="Select year (optional)" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-white/10">
                    <SelectItem value="2024">2024</SelectItem>
                    <SelectItem value="2025">2025</SelectItem>
                    <SelectItem value="2026">2026</SelectItem>
                    <SelectItem value="2027">2027</SelectItem>
                    <SelectItem value="2028">2028</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Skills */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Skills <span className="text-muted-foreground font-normal">(Press Enter to add)</span></label>
              <Input
                type="text"
                placeholder="e.g. React, Python, SQL..."
                className="glass rounded-lg border-white/10"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={handleAddSkill}
                disabled={loading}
              />
              {skills.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-2">
                  {skills.map((skill) => (
                    <div key={skill} className="bg-primary/20 text-primary px-3 py-1 rounded-full flex items-center gap-2 text-sm">
                      {skill}
                      <button type="button" onClick={() => setSkills(skills.filter(s => s !== skill))}
                        className="hover:text-primary/70 transition-colors">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Resume Upload */}
            <div className="space-y-1">
              <label className="text-sm font-medium">Upload Resume <span className="text-muted-foreground font-normal">(Optional, PDF/DOCX)</span></label>
              <Input
                type="file"
                accept=".pdf,.doc,.docx"
                className="glass rounded-lg border-white/10 file:bg-primary/20 file:text-primary file:border-0 file:rounded-md file:px-3 file:py-1 file:mr-3 file:hover:bg-primary/30 transition-all cursor-pointer"
                onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                disabled={loading}
              />
              {resumeFile && (
                <p className="text-xs text-primary flex items-center gap-1 mt-1">
                  <CheckCircle2 className="w-3 h-3" /> Selected: {resumeFile.name}
                </p>
              )}
            </div>

            {/* Submit */}
            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-primary to-secondary hover:opacity-90 text-white font-semibold h-11 rounded-lg transition-all duration-200 text-base"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating Account...</>
              ) : (
                <><CheckCircle2 className="w-4 h-4 mr-2" /> Create Account</>
              )}
            </Button>
          </form>

          <p className="text-sm text-center text-muted-foreground">
            Already have an account?{' '}
            <Link href="/login" className="text-primary hover:text-primary/80 transition-colors font-semibold">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
