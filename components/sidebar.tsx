'use client'

import {
  BarChart3,
  Bot,
  FileText,
  LogOut,
  Mail,
  Settings,
  Zap,
} from 'lucide-react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { useAuth } from '@/context/auth-context'

const menuItems = [
  { label: 'Dashboard', href: '/dashboard', icon: BarChart3 },
  { label: 'Applications', href: '/applications', icon: Mail },
  { label: 'Resume Manager', href: '/resume', icon: FileText },
  { label: 'AI Assistant', href: '/assistant', icon: Bot },
  { label: 'Cold Email', href: '/cold-email', icon: Mail },
  { label: 'Automation', href: '/automation', icon: Zap },
  { label: 'Settings', href: '/settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout } = useAuth()

  const handleLogout = () => {
    logout()
    router.push('/login')
  }

  const getInitials = (name?: string) => {
    if (!name) return 'U'
    return name.split(' ').map((n) => n[0]).join('').substring(0, 2).toUpperCase()
  }

  const avatarContent = user?.profile_picture ? (
    <img
      src={user.profile_picture.startsWith('http') ? user.profile_picture : `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'}${user.profile_picture}`}
      alt={user.full_name || 'User Avatar'}
      className="w-8 h-8 rounded-full object-cover border border-primary/30"
    />
  ) : (
    <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold text-xs ring-1 ring-primary/30">
      {getInitials(user?.full_name)}
    </div>
  )

  return (
    <aside className="hidden md:flex w-64 bg-card border-r border-border flex-col h-screen sticky top-0 glass">
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <img
            src="/logo.png"
            alt="SmartIntern logo"
            className="w-10 h-10 object-contain flex-shrink-0"
          />
          <div>
            <h1 className="text-lg font-bold glow text-primary leading-tight">SmartIntern</h1>
            <p className="text-xs text-muted-foreground">Tracker</p>
          </div>
        </div>
      </div>

      <div className="p-4 border-b border-border/50 flex items-center gap-3">
        {avatarContent}
        <div className="flex flex-col min-w-0">
          <span className="text-sm font-medium truncate text-foreground">{user?.full_name || 'User'}</span>
          <span className="text-xs text-muted-foreground truncate">{user?.email || 'Loading...'}</span>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto p-4 space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200',
                isActive
                  ? 'bg-primary/20 text-primary glow'
                  : 'text-muted-foreground hover:bg-white/5 hover:text-foreground'
              )}
            >
              <Icon className="w-5 h-5" />
              <span className="font-medium">{item.label}</span>
            </Link>
          )
        })}
      </nav>

      <div className="p-4 border-t border-border space-y-2">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-muted-foreground hover:bg-white/5 hover:text-red-400 transition-all duration-200"
        >
          <LogOut className="w-5 h-5" />
          <span className="font-medium">Logout</span>
        </button>
      </div>
    </aside>
  )
}
