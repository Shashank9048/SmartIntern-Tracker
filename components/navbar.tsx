'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/context/auth-context'
import { NotificationBell } from '@/components/notifications/notification-bell'
import { getApiBaseUrl } from '@/lib/api-client'

export function Navbar() {
  const { user } = useAuth()
  const [mounted, setMounted] = useState(false)

  useEffect(() => { setMounted(true) }, [])

  const getInitials = (name?: string) => {
    if (!name) return 'U'
    return name.split(' ').map((n) => n[0]).join('').substring(0, 2).toUpperCase()
  }

  const avatarContent = user?.profile_picture ? (
    <img
      src={user.profile_picture.startsWith('http') ? user.profile_picture : `${getApiBaseUrl()}${user.profile_picture}`}
      alt={user.full_name || 'User Avatar'}
      className="w-10 h-10 rounded-full object-cover border-2 border-primary/50"
    />
  ) : (
    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-secondary glow flex items-center justify-center text-white font-bold text-sm">
      {getInitials(user?.full_name)}
    </div>
  )

  const brand = (
    <div className="flex items-center gap-2.5">
      <img
        src="/logo.png"
        alt="SmartIntern"
        className="w-11 h-11 object-contain drop-shadow-lg"
      />
      <div className="flex flex-col leading-tight">
        <span className="text-base font-bold text-primary" style={{ textShadow: '0 0 12px currentColor' }}>
          SmartIntern
        </span>
        <span className="text-xs text-muted-foreground font-medium tracking-wide">Tracker</span>
      </div>
    </div>
  )

  if (!mounted) {
    return (
      <nav className="border-b border-border glass sticky top-0 z-50">
        <div className="px-5 py-3 flex items-center justify-between max-w-full">
          {brand}
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-secondary glow opacity-50" />
        </div>
      </nav>
    )
  }

  return (
    <nav className="border-b border-border glass sticky top-0 z-50">
      <div className="px-5 py-3 flex items-center justify-between max-w-full">
        {brand}
        <div className="flex items-center gap-4">
          <NotificationBell />
          {avatarContent}
        </div>
      </div>
    </nav>
  )
}
