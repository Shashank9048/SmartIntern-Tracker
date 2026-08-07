'use client'

import { useEffect, useState } from 'react'
import { Bell, CheckCircle2, CalendarDays, Briefcase, Mail } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { APIClient } from '@/lib/api-client'
import { AppNotification } from '@/types'
import { useAuth } from '@/context/auth-context'

export function NotificationBell() {
  const { user } = useAuth()
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    if (!user) return

    const fetchNotifications = async () => {
      try {
        const data = await APIClient.get<AppNotification[]>('/api/notifications')
        setNotifications(data)
        setUnreadCount(data.filter(n => !n.read_bool).length)
      } catch (error) {
        // Silently ignore network errors (backend unreachable) — bell stays quiet
        if (error instanceof Error && (error.name === 'NetworkError' || error.message.startsWith('NetworkError'))) return
        console.warn('[NotificationBell] Failed to fetch notifications:', error)
      }
    }

    fetchNotifications()
    // Could poll every minute here if desired
    const interval = setInterval(fetchNotifications, 60000)
    return () => clearInterval(interval)
  }, [user])

  const handleMarkRead = async (id: string) => {
    try {
      await APIClient.patch(`/api/notifications/${id}/read`)
      setNotifications(prev => 
        prev.map(n => n.id === id ? { ...n, read_bool: true } : n)
      )
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch (error) {
      console.error('Failed to mark notification as read', error)
    }
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'digest': return <Mail className="w-4 h-4 text-emerald-400" />
      case 'deadline': return <CalendarDays className="w-4 h-4 text-rose-400" />
      case 'interview': return <Briefcase className="w-4 h-4 text-blue-400" />
      default: return <Bell className="w-4 h-4 text-amber-400" />
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="relative p-2 rounded-full hover:bg-white/5 transition-colors outline-none focus:ring-2 focus:ring-primary/50 cursor-pointer">
        <Bell className="w-5 h-5 text-muted-foreground hover:text-white transition-colors" />
        {unreadCount > 0 && (
          <span className="absolute top-1.5 right-1.5 w-4 h-4 flex items-center justify-center bg-rose-500 text-white text-[10px] font-bold rounded-full ring-2 ring-[#09090b]">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </DropdownMenuTrigger>
      
      <DropdownMenuContent align="end" className="w-80 bg-[#09090b] border-white/10 p-0 overflow-hidden shadow-2xl">
        <div className="px-4 py-3 border-b border-white/5 bg-white/5 flex items-center justify-between">
          <h3 className="font-semibold text-sm">Notifications</h3>
          {unreadCount > 0 && (
            <span className="text-xs text-muted-foreground">{unreadCount} unread</span>
          )}
        </div>
        
        <div className="max-h-[400px] overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground flex flex-col items-center gap-2">
              <CheckCircle2 className="w-8 h-8 text-white/10" />
              You're all caught up!
            </div>
          ) : (
            notifications.map((notif) => (
              <DropdownMenuItem
                key={notif.id}
                onClick={() => !notif.read_bool && handleMarkRead(notif.id)}
                className={`px-4 py-3 flex items-start gap-3 border-b border-white/5 cursor-pointer focus:bg-white/5 ${
                  !notif.read_bool ? 'bg-primary/5' : 'opacity-75'
                }`}
              >
                <div className={`mt-0.5 p-1.5 rounded-full ${!notif.read_bool ? 'bg-white/10' : 'bg-transparent'}`}>
                  {getIcon(notif.type)}
                </div>
                <div className="flex-1 flex flex-col gap-1">
                  <p className={`text-sm leading-snug ${!notif.read_bool ? 'text-white' : 'text-muted-foreground'}`}>
                    {notif.payload.message || 'New notification'}
                  </p>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    {new Date(notif.created_at).toLocaleDateString(undefined, { 
                      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' 
                    })}
                  </span>
                </div>
                {!notif.read_bool && (
                  <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                )}
              </DropdownMenuItem>
            ))
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
