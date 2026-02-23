'use client'

import { AppLayout } from '@/components/app-layout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Copy, RotateCcw, Zap } from 'lucide-react'
import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { GeminiService } from '@/lib/gemini-service'

export default function ColdEmailGeneratorPage() {
  const [formData, setFormData] = useState({
    recruiterName: '',
    companyName: '',
    role: '',
    skills: '',
    interest: '',
  })
  const [generatedEmail, setGeneratedEmail] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('company') || params.get('role')) {
      setFormData(prev => ({
        ...prev,
        companyName: params.get('company') || prev.companyName,
        role: params.get('role') || prev.role,
      }));
    }
  }, []);

  const handleGenerate = async () => {
    if (!formData.recruiterName || !formData.companyName || !formData.role) {
      toast.error('Please fill in required fields')
      return
    }

    setLoading(true)
    try {
      const response = await GeminiService.generateColdEmail({
        recruiterName: formData.recruiterName,
        companyName: formData.companyName,
        position: formData.role,
        userBackground: `Skills: ${formData.skills}. Interest: ${formData.interest}`,
      })
      setGeneratedEmail(response.body)
      toast.success('Email generated successfully!')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to generate email')
      // Fallback email for demo
      setGeneratedEmail(`Hi ${formData.recruiterName},

I hope this email finds you well. I'm writing to express my strong interest in the ${formData.role} position at ${formData.companyName}.

As a dedicated student with a passion for technology and problem-solving, I'm excited about the opportunity to contribute to your team. I have developed strong skills in ${formData.skills || 'various technical areas'} and I'm eager to apply these abilities in a professional setting.

What particularly excites me about ${formData.companyName} is ${formData.interest || 'your innovative approach to technology and customer-centric solutions'}. I believe my background and enthusiasm make me a great fit for this role.

I would welcome the opportunity to discuss how I can contribute to your team. Please feel free to reach out at your convenience.

Thank you for considering my application. I look forward to hearing from you.

Best regards,
[Your Name]`)
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(generatedEmail)
    toast.success('Email copied to clipboard!')
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold mb-2">Cold Email Generator</h1>
          <p className="text-muted-foreground">
            Generate personalized cold emails to recruiters
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Form */}
          <div className="lg:col-span-1">
            <div className="glass rounded-xl p-6 glow space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Recruiter Name *</label>
                <Input
                  type="text"
                  placeholder="John Doe"
                  className="glass border-white/10 rounded-lg"
                  value={formData.recruiterName}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      recruiterName: e.target.value,
                    })
                  }
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Company Name *</label>
                <Input
                  type="text"
                  placeholder="Google"
                  className="glass border-white/10 rounded-lg"
                  value={formData.companyName}
                  onChange={(e) =>
                    setFormData({ ...formData, companyName: e.target.value })
                  }
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Role *</label>
                <Input
                  type="text"
                  placeholder="Software Engineer Intern"
                  className="glass border-white/10 rounded-lg"
                  value={formData.role}
                  onChange={(e) =>
                    setFormData({ ...formData, role: e.target.value })
                  }
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Your Skills</label>
                <Input
                  type="text"
                  placeholder="React, Python, SQL"
                  className="glass border-white/10 rounded-lg"
                  value={formData.skills}
                  onChange={(e) =>
                    setFormData({ ...formData, skills: e.target.value })
                  }
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">
                  Why Interested
                </label>
                <textarea
                  placeholder="What excites you about this company?"
                  className="w-full h-24 bg-white/5 border border-white/10 rounded-lg p-3 text-sm focus:outline-none focus:border-primary/50 resize-none"
                  value={formData.interest}
                  onChange={(e) =>
                    setFormData({ ...formData, interest: e.target.value })
                  }
                />
              </div>

              <Button
                onClick={handleGenerate}
                disabled={loading}
                className="w-full bg-gradient-to-r from-primary to-secondary hover:opacity-90 text-white"
              >
                <Zap className="w-4 h-4 mr-2" />
                {loading ? 'Generating...' : 'Generate Email'}
              </Button>
            </div>
          </div>

          {/* Preview */}
          <div className="lg:col-span-2">
            <div className="glass rounded-xl p-6 glow">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Email Preview</h3>
                {generatedEmail && (
                  <div className="flex gap-2">
                    <Button
                      onClick={handleCopy}
                      variant="outline"
                      size="sm"
                      className="border-white/10 hover:bg-white/5 bg-transparent"
                    >
                      <Copy className="w-4 h-4 mr-2" />
                      Copy
                    </Button>
                    <Button
                      onClick={() => setGeneratedEmail('')}
                      variant="outline"
                      size="sm"
                      className="border-white/10 hover:bg-white/5"
                    >
                      <RotateCcw className="w-4 h-4 mr-2" />
                      Regenerate
                    </Button>
                  </div>
                )}
              </div>

              {generatedEmail ? (
                <div className="bg-white/5 border border-white/10 rounded-lg p-6 whitespace-pre-wrap text-sm leading-relaxed">
                  {generatedEmail}
                </div>
              ) : (
                <div className="bg-white/5 border border-dashed border-white/10 rounded-lg p-12 text-center text-muted-foreground">
                  <p>Your generated email will appear here</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
