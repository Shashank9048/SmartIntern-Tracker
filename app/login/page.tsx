'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import Link from 'next/link'
import { Eye, EyeOff } from 'lucide-react'
import { useAuth } from '@/context/auth-context'
import { toast } from 'sonner'
import Script from 'next/script'

declare global {
  namespace JSX {
    interface IntrinsicElements {
      'g_id_onload': any
      'g_signin_button': any
    }
  }
}

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [email, setEmail] = useState('shashanksingh9048@gmail.com')
  const [password, setPassword] = useState('Arise')
  const { login, loginWithGoogle } = useAuth()
  const router = useRouter()

  React.useEffect(() => {
    // Check if email was passed from signup redirect
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const emailParam = params.get('email')
      if (emailParam) {
        setEmail(decodeURIComponent(emailParam))
      }
    }
  }, [])



  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      toast.error('Please fill in all fields')
      return
    }

    setLoading(true)
    try {
      // Use the AuthContext login() which now stores token + loads profile
      await login(email.trim(), password)

      toast.success('Login successful!')

      // Respect ?next= redirect if middleware bounced user here
      const params = new URLSearchParams(window.location.search)
      const nextPath = params.get('next') || '/dashboard'
      router.push(nextPath)
    } catch (error) {
      console.error('Login Error:', error)
      toast.error(error instanceof Error ? error.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSignIn = async (response: any) => {
    // Keeping this as is for now, using useAuth as I didn't reimplement Google Auth
    setLoading(true)
    try {
      await loginWithGoogle(response.credential)
      toast.success('Login successful!')
      router.push('/dashboard')
    } catch (error) {
      console.error('Google Login Error:', error)
      toast.error(error instanceof Error ? error.message : 'Google login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 w-full max-w-6xl">
        {/* Left side - Branding */}
        <div className="hidden lg:flex flex-col justify-center space-y-8">
          <div>
            <h1 className="text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent mb-4">
              InternTrack
            </h1>
            <p className="text-xl text-muted-foreground">
              AI-Powered Internship Application Tracking
            </p>
          </div>

          <div className="space-y-6">
            <div className="flex gap-4">
              <div className="w-12 h-12 rounded-lg bg-primary/20 glow flex items-center justify-center">
                <span className="text-primary font-bold">✓</span>
              </div>
              <div>
                <h3 className="font-semibold mb-1">Smart Resume Analysis</h3>
                <p className="text-sm text-muted-foreground">
                  AI-powered resume matching with job descriptions
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <div className="w-12 h-12 rounded-lg bg-secondary/20 glow flex items-center justify-center">
                <span className="text-secondary font-bold">⚡</span>
              </div>
              <div>
                <h3 className="font-semibold mb-1">Track Applications</h3>
                <p className="text-sm text-muted-foreground">
                  Manage all your internship applications in one place
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <div className="w-12 h-12 rounded-lg bg-accent/20 glow flex items-center justify-center">
                <span className="text-accent font-bold">🎯</span>
              </div>
              <div>
                <h3 className="font-semibold mb-1">AI Insights</h3>
                <p className="text-sm text-muted-foreground">
                  Get personalized recommendations to improve your applications
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col justify-center">
          <div className="glass p-8 rounded-2xl space-y-6">
            <div>
              <h2 className="text-3xl font-bold mb-2">Welcome Back</h2>
              <p className="text-muted-foreground">Sign in to your account to continue</p>
            </div>

            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <label className="block text-sm font-medium">Email</label>
                <Input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="bg-white/5 border-white/10 text-foreground placeholder:text-muted-foreground"
                />
              </div>

              <div className="space-y-2">
                <label className="block text-sm font-medium">Password</label>
                <div className="relative">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="bg-white/5 border-white/10 text-foreground placeholder:text-muted-foreground pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-2.5 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-sm">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="rounded" />
                  <span className="text-muted-foreground">Remember me</span>
                </label>
                <Link
                  href="/forgot-password"
                  className="text-primary hover:text-primary/80 transition-colors"
                >
                  Forgot password?
                </Link>
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full bg-primary hover:bg-primary/90 text-white"
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </Button>
            </form>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-white/10" />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-card text-muted-foreground">OR</span>
              </div>
            </div>

            <div id="google-signin-container" className="flex justify-center">
              <Script
                src="https://accounts.google.com/gsi/client"
                strategy="afterInteractive"
                onLoad={() => {
                  if (typeof window !== 'undefined' && (window as any).google) {
                    (window as any).google.accounts.id.initialize({
                      client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '',
                      callback: handleGoogleSignIn,
                    })
                      ; (window as any).google.accounts.id.renderButton(
                        document.getElementById('google-signin-container'),
                        {
                          theme: 'filled_black',
                          size: 'large',
                          text: 'signin',
                        }
                      )
                  }
                }}
              />
            </div>

            <p className="text-sm text-center text-muted-foreground">
              Don't have an account?{' '}
              <Link
                href="/signup"
                className="text-primary hover:text-primary/80 transition-colors font-semibold"
              >
                Sign up
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
