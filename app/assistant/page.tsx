'use client'

import { AppLayout } from '@/components/app-layout'
import { AIChatbot } from '@/components/assistant/ai-chatbot'
import { AIInsights } from '@/components/dashboard/ai-insights'

export default function AssistantPage() {
  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold mb-2">AI Assistant</h1>
          <p className="text-muted-foreground">
            Get personalized career advice and interview preparation tips
          </p>
        </div>

        {/* AI Career Coach Insights */}
        <AIInsights />

        {/* Chatbot */}
        <AIChatbot />
      </div>
    </AppLayout>
  )
}
