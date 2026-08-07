'use client'

import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Link from 'next/link'
import { Mail, ArrowLeft, Loader2, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'
import { getApiBaseUrl } from '@/lib/api-client'

const API_URL = typeof window !== 'undefined' ? getApiBaseUrl() : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')

type Step = 'email' | 'otp' | 'new-password' | 'done'

export default function ForgotPasswordPage() {
    const [step, setStep] = useState<Step>('email')
    const [email, setEmail] = useState('')
    const [otp, setOtp] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [loading, setLoading] = useState(false)

    // Step 1: Send OTP
    const handleSendOTP = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!email.trim()) { toast.error('Please enter your email'); return }
        setLoading(true)
        try {
            const res = await fetch(`${API_URL}/auth/forgot-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email.trim() }),
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data?.detail || 'Failed to send reset email')
            toast.success('OTP sent! Check your email inbox.')
            setStep('otp')
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to send OTP')
        } finally {
            setLoading(false)
        }
    }

    // Step 2: Verify OTP
    const handleVerifyOTP = async (e: React.FormEvent) => {
        e.preventDefault()
        if (otp.length < 4) { toast.error('Please enter the OTP from your email'); return }
        setLoading(true)
        try {
            const res = await fetch(`${API_URL}/auth/verify-otp`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email.trim(), otp }),
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data?.detail || 'Invalid or expired OTP')
            toast.success('OTP verified! Set your new password.')
            setStep('new-password')
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'OTP verification failed')
        } finally {
            setLoading(false)
        }
    }

    // Step 3: Reset Password
    const handleResetPassword = async (e: React.FormEvent) => {
        e.preventDefault()
        if (newPassword.length < 6) { toast.error('Password must be at least 6 characters'); return }
        if (newPassword !== confirmPassword) { toast.error('Passwords do not match'); return }
        setLoading(true)
        try {
            const res = await fetch(`${API_URL}/auth/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email.trim(), otp, new_password: newPassword }),
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data?.detail || 'Failed to reset password')
            toast.success('Password reset successfully!')
            setStep('done')
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Password reset failed')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-background flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                <div className="glass rounded-2xl p-8 space-y-6 glow">

                    {/* Header */}
                    <div>
                        <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary mb-2">
                            SmartIntern
                        </h1>
                        <h2 className="text-xl font-bold mb-1">
                            {step === 'done' ? 'Password Reset!' : 'Forgot Password?'}
                        </h2>
                        <p className="text-muted-foreground text-sm">
                            {step === 'email' && "Enter your email and we'll send you a reset code."}
                            {step === 'otp' && `We sent a 6-digit code to ${email}`}
                            {step === 'new-password' && 'Choose a strong new password.'}
                            {step === 'done' && 'You can now log in with your new password.'}
                        </p>
                    </div>

                    {/* Step indicator */}
                    <div className="flex items-center gap-2">
                        {(['email', 'otp', 'new-password'] as Step[]).map((s, i) => (
                            <React.Fragment key={s}>
                                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all ${step === s ? 'border-primary bg-primary text-white' :
                                        (['email', 'otp', 'new-password', 'done'].indexOf(step) > i) ? 'border-green-500 bg-green-500/20 text-green-400' :
                                            'border-white/20 text-white/30'
                                    }`}>{i + 1}</div>
                                {i < 2 && <div className={`flex-1 h-0.5 transition-all ${(['email', 'otp', 'new-password', 'done'].indexOf(step) > i) ? 'bg-green-500' : 'bg-white/10'}`} />}
                            </React.Fragment>
                        ))}
                    </div>

                    {/* Step 1: Email */}
                    {step === 'email' && (
                        <form onSubmit={handleSendOTP} className="space-y-4">
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Email Address</label>
                                <div className="relative">
                                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                    <Input
                                        type="email"
                                        placeholder="you@example.com"
                                        className="glass rounded-lg border-white/10 pl-10"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        disabled={loading}
                                        required
                                    />
                                </div>
                            </div>
                            <Button type="submit" disabled={loading} className="w-full bg-gradient-to-r from-primary to-secondary text-white h-11">
                                {loading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Sending...</> : 'Send Reset Code'}
                            </Button>
                        </form>
                    )}

                    {/* Step 2: OTP */}
                    {step === 'otp' && (
                        <form onSubmit={handleVerifyOTP} className="space-y-4">
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Enter OTP</label>
                                <Input
                                    type="text"
                                    placeholder="Enter the 6-digit code"
                                    className="glass rounded-lg border-white/10 text-center text-2xl tracking-widest font-mono"
                                    value={otp}
                                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                    maxLength={6}
                                    disabled={loading}
                                    required
                                />
                                <p className="text-xs text-muted-foreground text-center">Check your spam folder if not found</p>
                            </div>
                            <Button type="submit" disabled={loading || otp.length < 4} className="w-full bg-gradient-to-r from-primary to-secondary text-white h-11">
                                {loading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Verifying...</> : 'Verify Code'}
                            </Button>
                            <button type="button" onClick={() => { setOtp(''); handleSendOTP({ preventDefault: () => { } } as any) }}
                                className="w-full text-sm text-muted-foreground hover:text-primary transition-colors text-center">
                                Resend code
                            </button>
                        </form>
                    )}

                    {/* Step 3: New Password */}
                    {step === 'new-password' && (
                        <form onSubmit={handleResetPassword} className="space-y-4">
                            <div className="space-y-1">
                                <label className="text-sm font-medium">New Password</label>
                                <Input
                                    type="password"
                                    placeholder="Min. 6 characters"
                                    className="glass rounded-lg border-white/10"
                                    value={newPassword}
                                    onChange={(e) => setNewPassword(e.target.value)}
                                    disabled={loading}
                                    required
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Confirm Password</label>
                                <Input
                                    type="password"
                                    placeholder="Re-enter password"
                                    className="glass rounded-lg border-white/10"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    disabled={loading}
                                    required
                                />
                            </div>
                            <Button type="submit" disabled={loading} className="w-full bg-gradient-to-r from-primary to-secondary text-white h-11">
                                {loading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Resetting...</> : 'Reset Password'}
                            </Button>
                        </form>
                    )}

                    {/* Step 4: Done */}
                    {step === 'done' && (
                        <div className="flex flex-col items-center gap-4 py-4">
                            <CheckCircle2 className="w-16 h-16 text-green-400" />
                            <p className="text-center text-muted-foreground text-sm">Your password has been reset successfully!</p>
                            <Link href="/login" className="w-full">
                                <Button className="w-full bg-gradient-to-r from-primary to-secondary text-white h-11">
                                    Go to Login
                                </Button>
                            </Link>
                        </div>
                    )}

                    {/* Back to login */}
                    {step !== 'done' && (
                        <Link href="/login" className="flex items-center justify-center gap-1 text-sm text-muted-foreground hover:text-primary transition-colors">
                            <ArrowLeft className="w-4 h-4" /> Back to Login
                        </Link>
                    )}

                </div>
            </div>
        </div>
    )
}
