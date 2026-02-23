'use client'

import { AppLayout } from '@/components/app-layout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Camera, Lock, User, Loader2, X, Plus, CheckCircle2, Shield, AlertTriangle, Trash2 } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { getUserProfile, updateUserProfile, changePassword, uploadAvatar, deleteUserProfile, UserProfile } from '../../src/services/api'
import { useAuth } from '@/context/auth-context'
import { toast } from 'sonner'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function SettingsPage() {
  const { refreshUser, logout } = useAuth()
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [changingPw, setChangingPw] = useState(false)
  const [uploadingAvatar, setUploadingAvatar] = useState(false)
  const [savingNotifs, setSavingNotifs] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deletingAccount, setDeletingAccount] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [skillInput, setSkillInput] = useState('')

  const [profile, setProfile] = useState<UserProfile>({
    email: '',
    full_name: '',
    skills: [],
    preferences: {
      theme: 'dark',
      notifications: { email: true, interview: true, marketing: false },
    },
  })

  const [passwords, setPasswords] = useState({ current: '', new: '', confirm: '' })

  // ── Load ─────────────────────────────────────────────────────────────────────

  useEffect(() => { loadProfile() }, [])

  const loadProfile = async () => {
    try {
      const data = await getUserProfile()
      setProfile(data)
    } catch {
      toast.error('Failed to load profile. Please refresh the page.')
    } finally {
      setLoading(false)
    }
  }

  // ── Save profile (name + skills) ─────────────────────────────────────────────

  const handleSaveProfile = async () => {
    if (!profile.full_name.trim()) {
      toast.error('Name cannot be empty')
      return
    }
    setSaving(true)
    try {
      const updated = await updateUserProfile({
        full_name: profile.full_name.trim(),
        skills: profile.skills,
      })
      setProfile(updated)
      await refreshUser()
      toast.success('Profile saved!')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to save profile')
    } finally {
      setSaving(false)
    }
  }

  // ── Skills ────────────────────────────────────────────────────────────────────

  const handleAddSkill = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      const s = skillInput.trim()
      if (s && !profile.skills.includes(s)) {
        setProfile(prev => ({ ...prev, skills: [...prev.skills, s] }))
        setSkillInput('')
      }
    }
  }

  const removeSkill = (skill: string) => {
    setProfile(prev => ({ ...prev, skills: prev.skills.filter(s => s !== skill) }))
  }

  // ── Change password ───────────────────────────────────────────────────────────

  const handleChangePassword = async () => {
    if (!passwords.current || !passwords.new || !passwords.confirm) {
      toast.error('Please fill in all password fields')
      return
    }
    if (passwords.new !== passwords.confirm) {
      toast.error('New passwords do not match')
      return
    }
    if (passwords.new.length < 6) {
      toast.error('Password must be at least 6 characters')
      return
    }
    setChangingPw(true)
    try {
      await changePassword(passwords.current, passwords.new)
      toast.success('Password changed successfully!')
      setPasswords({ current: '', new: '', confirm: '' })
    } catch (err: any) {
      toast.error(err?.message || 'Failed to change password. Check your current password.')
    } finally {
      setChangingPw(false)
    }
  }

  // ── Avatar upload ─────────────────────────────────────────────────────────────

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) { toast.error('Please upload an image file'); return }
    if (file.size > 5 * 1024 * 1024) { toast.error('Image must be less than 5MB'); return }

    setUploadingAvatar(true)
    try {
      const response = await uploadAvatar(file)
      // uploadAvatar returns { profile_picture_url: string }
      setProfile(prev => ({ ...prev, profile_picture: response.profile_picture_url }))
      await refreshUser()
      toast.success('Profile picture updated!')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to upload profile picture')
    } finally {
      setUploadingAvatar(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // ── Notification preferences ─────────────────────────────────────────────────

  const handleNotifChange = async (key: 'email' | 'interview' | 'marketing', value: boolean) => {
    const updatedNotifs = { ...(profile.preferences?.notifications || { email: true, interview: true, marketing: false }), [key]: value }
    const updatedPrefs = { theme: profile.preferences?.theme || 'dark', notifications: updatedNotifs }
    // Optimistic update
    setProfile(prev => ({ ...prev, preferences: updatedPrefs }))
    setSavingNotifs(true)
    try {
      await updateUserProfile({ preferences: updatedPrefs as any })
    } catch {
      // Revert on failure
      toast.error('Failed to save notification preference')
      loadProfile()
    } finally {
      setSavingNotifs(false)
    }
  }

  // ── Delete Account ───────────────────────────────────────────────────────────

  const handleDeleteAccount = async () => {
    if (deleteConfirmText !== 'DELETE') return
    setDeletingAccount(true)
    try {
      await deleteUserProfile()
      toast.success('Account deleted. Goodbye!')
      logout()
      router.push('/login')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to delete account')
      setDeletingAccount(false)
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-sm">Loading settings...</p>
          </div>
        </div>
      </AppLayout>
    )
  }

  return (
    <AppLayout>
      <div className="space-y-6 max-w-3xl pb-12">

        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold mb-1">Settings</h1>
          <p className="text-muted-foreground text-sm">Manage your account, profile, and preferences</p>
        </div>

        {/* ── Profile Section ───────────────────────────────────────────────── */}
        <div className="glass rounded-xl p-6 glow">
          <div className="flex items-center gap-2 mb-6">
            <User className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-semibold">Profile</h3>
          </div>

          <div className="flex flex-col sm:flex-row gap-6 mb-6">
            {/* Avatar */}
            <div className="flex-shrink-0">
              <div
                className={`w-24 h-24 rounded-full border-4 border-white/10 overflow-hidden bg-white/5 flex items-center justify-center relative group ${uploadingAvatar ? 'opacity-60 cursor-wait' : 'cursor-pointer'}`}
                onClick={() => !uploadingAvatar && fileInputRef.current?.click()}
              >
                {profile.profile_picture ? (
                  <img
                    src={profile.profile_picture.startsWith('http') ? profile.profile_picture : `${API_URL}${profile.profile_picture}`}
                    alt="Profile"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <User className="w-10 h-10 text-muted-foreground" />
                )}
                {uploadingAvatar ? (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                    <Loader2 className="w-5 h-5 animate-spin text-primary" />
                  </div>
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Camera className="w-5 h-5 text-white" />
                  </div>
                )}
              </div>
              <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
              <p className="text-xs text-muted-foreground mt-2 text-center">Click to change</p>
            </div>

            {/* Name + Email */}
            <div className="flex-1 space-y-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">Full Name</label>
                <Input
                  type="text"
                  value={profile.full_name}
                  onChange={(e) => setProfile(prev => ({ ...prev, full_name: e.target.value }))}
                  className="glass border-white/10 rounded-lg"
                  placeholder="Your full name"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Email Address</label>
                <Input
                  type="email"
                  value={profile.email}
                  disabled
                  className="glass border-white/10 rounded-lg opacity-60 cursor-not-allowed"
                />
                <p className="text-xs text-muted-foreground">Email cannot be changed</p>
              </div>
            </div>
          </div>

          {/* Skills */}
          <div className="space-y-2 mb-6">
            <label className="text-sm font-medium">Skills <span className="text-muted-foreground font-normal">(Press Enter to add)</span></label>
            <div className="relative">
              <Plus className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="e.g. React, Python, SQL..."
                className="glass border-white/10 rounded-lg pl-9"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={handleAddSkill}
              />
            </div>
            {profile.skills.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {profile.skills.map((skill) => (
                  <div key={skill} className="bg-primary/20 text-primary px-3 py-1 rounded-full flex items-center gap-2 text-sm border border-primary/20">
                    {skill}
                    <button type="button" onClick={() => removeSkill(skill)} className="hover:text-red-400 transition-colors">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Button onClick={handleSaveProfile} disabled={saving} className="bg-primary hover:bg-primary/90 text-white">
            {saving ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving...</> : <><CheckCircle2 className="w-4 h-4 mr-2" />Save Profile</>}
          </Button>
        </div>

        {/* ── Change Password ───────────────────────────────────────────────── */}
        <div className="glass rounded-xl p-6 glow">
          <div className="flex items-center gap-2 mb-6">
            <Lock className="w-5 h-5 text-accent" />
            <h3 className="text-lg font-semibold">Change Password</h3>
          </div>

          <div className="space-y-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">Current Password</label>
              <Input
                type="password"
                placeholder="••••••••"
                value={passwords.current}
                onChange={(e) => setPasswords(p => ({ ...p, current: e.target.value }))}
                className="glass border-white/10 rounded-lg"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-sm font-medium">New Password</label>
                <Input
                  type="password"
                  placeholder="Min. 6 characters"
                  value={passwords.new}
                  onChange={(e) => setPasswords(p => ({ ...p, new: e.target.value }))}
                  className="glass border-white/10 rounded-lg"
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm font-medium">Confirm New Password</label>
                <Input
                  type="password"
                  placeholder="Re-enter new password"
                  value={passwords.confirm}
                  onChange={(e) => setPasswords(p => ({ ...p, confirm: e.target.value }))}
                  className="glass border-white/10 rounded-lg"
                />
              </div>
            </div>
            <Button onClick={handleChangePassword} disabled={changingPw} className="bg-primary hover:bg-primary/90 text-white">
              {changingPw ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Updating...</> : <><Shield className="w-4 h-4 mr-2" />Update Password</>}
            </Button>
          </div>
        </div>

        {/* ── Notification Preferences ──────────────────────────────────────── */}
        <div className="glass rounded-xl p-6 glow">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold">Notification Preferences</h3>
            {savingNotifs && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
          </div>

          <div className="space-y-3">
            {[
              { key: 'email' as const, label: 'Email Notifications', desc: 'Receive updates about your applications' },
              { key: 'interview' as const, label: 'Interview Reminders', desc: 'Get notified about upcoming interviews' },
              { key: 'marketing' as const, label: 'Product Updates', desc: 'Tips and updates from SmartIntern' },
            ].map(({ key, label, desc }) => (
              <div key={key} className="flex items-center justify-between p-4 rounded-lg bg-white/5 border border-white/10">
                <div>
                  <p className="font-medium text-sm">{label}</p>
                  <p className="text-xs text-muted-foreground">{desc}</p>
                </div>
                <Switch
                  checked={profile.preferences?.notifications?.[key] ?? (key !== 'marketing')}
                  onCheckedChange={(v) => handleNotifChange(key, v)}
                  disabled={savingNotifs}
                />
              </div>
            ))}
          </div>
        </div>

        {/* ── Danger Zone ───────────────────────────────────────────────────── */}
        <div className="glass rounded-xl p-6 border border-red-500/30">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <h3 className="text-lg font-semibold text-red-400">Danger Zone</h3>
          </div>
          <p className="text-sm text-muted-foreground mb-4">
            Permanently delete your account and <strong className="text-foreground">all associated data</strong> — applications, automations, resume, and profile. This cannot be undone.
          </p>
          <Button
            variant="outline"
            className="border-red-500/40 text-red-400 hover:bg-red-500/15 hover:border-red-500/60 bg-transparent transition-all"
            onClick={() => { setShowDeleteModal(true); setDeleteConfirmText('') }}
          >
            <Trash2 className="w-4 h-4 mr-2" /> Delete My Account
          </Button>
        </div>

      </div>

      {/* ── Delete Confirmation Modal ──────────────────────────────────────── */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => !deletingAccount && setShowDeleteModal(false)} />
          <div className="relative glass rounded-2xl p-6 w-full max-w-md shadow-2xl border border-red-500/30">
            <button
              onClick={() => setShowDeleteModal(false)}
              disabled={deletingAccount}
              className="absolute top-4 right-4 text-muted-foreground hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="w-11 h-11 rounded-full bg-red-950/60 border border-red-900/50 flex items-center justify-center flex-shrink-0">
                <Trash2 className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="font-bold text-white text-lg">Delete Account</h3>
                <p className="text-xs text-muted-foreground">This is permanent and cannot be reversed</p>
              </div>
            </div>

            <div className="bg-red-950/30 border border-red-900/40 rounded-lg p-3 mb-5 text-sm text-red-300">
              ⚠️ All your <strong>applications, automations, resume data</strong>, and profile will be <strong>permanently deleted</strong>.
            </div>

            <div className="space-y-2 mb-5">
              <label className="text-sm font-medium">
                Type <span className="font-mono font-bold text-red-400 bg-red-950/40 px-1.5 py-0.5 rounded">DELETE</span> to confirm
              </label>
              <Input
                type="text"
                placeholder="Type DELETE here"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                className="glass border-red-500/30 focus:border-red-500/60 rounded-lg font-mono"
                disabled={deletingAccount}
                autoFocus
              />
            </div>

            <div className="flex gap-3">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowDeleteModal(false)}
                disabled={deletingAccount}
              >
                Cancel
              </Button>
              <Button
                className="flex-1 bg-red-600 hover:bg-red-700 text-white border-0 disabled:opacity-40 disabled:cursor-not-allowed"
                disabled={deleteConfirmText !== 'DELETE' || deletingAccount}
                onClick={handleDeleteAccount}
              >
                {deletingAccount ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Deleting...</>
                ) : (
                  <><Trash2 className="w-4 h-4 mr-2" />Delete Forever</>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

    </AppLayout>
  )
}
