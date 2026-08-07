'use client'

import React from "react"

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Send, Trash2 } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
// import { GeminiService } from '@/lib/gemini-service' // Deprecated
import { chatWithAI } from '@/src/services/api'
import { toast } from 'sonner'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export function AIChatbot() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hello! I\'m your AI Career Coach. I can review your resume, specific job descriptions, or answer career questions. How can I help you today?',
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [mounted, setMounted] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    const userInput = input
    setInput('')
    setLoading(true)

    try {
      const reply = await chatWithAI(userInput)

      // Check if backend returned an error string (legacy path, shouldn't happen after backend fix)
      if (reply && (reply.startsWith("Error:") || reply.startsWith("System Error:"))) {
        throw new Error("AI service is temporarily unavailable. Please try again in a moment.");
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: reply,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (error: unknown) {
      console.error("[Chat Error] handleSendMessage:", error)

      // Determine a clean, user-friendly message based on error type
      let friendlyMsg = "I'm having trouble connecting right now. Please try again in a moment."

      if (error instanceof Error) {
        const msg = error.message || ''
        if (msg.includes('503') || msg.includes('temporarily unavailable') || msg.includes('quota')) {
          friendlyMsg = "I'm temporarily unavailable — the AI models are at capacity. Please try again in a few minutes."
        } else if (msg.includes('401') || msg.includes('Unauthorized')) {
          friendlyMsg = "Your session has expired. Please log in again."
        } else if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('ECONNREFUSED')) {
          friendlyMsg = "Cannot reach the server. Please check your connection or ensure the backend is running."
        } else if (msg.includes('404')) {
          friendlyMsg = "The AI chat endpoint was not found. Please contact support."
        } else if (msg.length > 0 && msg.length < 120 && !msg.includes('{') && !msg.includes('NOT_FOUND')) {
          // Only surface the error message if it's short and clean (not raw JSON / API error)
          friendlyMsg = msg
        }
      }

      toast.error(friendlyMsg)

      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `⚠️ ${friendlyMsg}`,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleClearChat = () => {
    setMessages([
      {
        id: '1',
        role: 'assistant',
        content: 'Hello! I\'m your AI career assistant. I can help you with interview prep, resume tips, and job search strategies. What would you like to know?',
        timestamp: new Date(),
      },
    ])
  }

  return (
    <div className="flex flex-col h-[600px] glass rounded-xl glow">
      {/* Header */}
      <div className="p-4 border-b border-white/10 flex items-center justify-between">
        <h3 className="text-lg font-semibold">AI Career Assistant</h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleClearChat}
          className="hover:bg-white/5"
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
            >
              <div
                className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${message.role === 'user'
                  ? 'bg-primary/20 text-primary'
                  : 'bg-white/5 text-foreground'
                  }`}
              >
                <p className="text-sm">{message.content}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {/* Hydration fix: Only render time on client */}
                  {mounted ? message.timestamp.toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  }) : ''}
                </p>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white/5 px-4 py-2 rounded-lg">
                <div className="flex gap-2">
                  <div className="w-2 h-2 bg-accent rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-accent rounded-full animate-bounce delay-100" />
                  <div className="w-2 h-2 bg-accent rounded-full animate-bounce delay-200" />
                </div>
              </div>
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="p-4 border-t border-white/10">
        <form onSubmit={handleSendMessage} className="flex gap-2">
          <Input
            type="text"
            placeholder="Ask me anything about your job search..."
            className="flex-1 glass border-white/10 rounded-lg"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <Button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-primary hover:bg-primary/90 text-white"
          >
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </div>
    </div>
  )
}
