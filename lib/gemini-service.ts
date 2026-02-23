import { APIClient } from './api-client'

export interface GeminiRequest {
  prompt: string
  context?: string
  temperature?: number
  maxTokens?: number
}

export interface GeminiResponse {
  text: string
  tokens: {
    input: number
    output: number
  }
}

export interface ResumeAnalysisRequest {
  resumeText: string
  jobDescription: string
}

export interface ImprovementPriority {
  area: string
  priority: string
  action: string
}

export interface ResumeAnalysisResponse {
  match_score: number
  match_label: string
  skills_found: string[]
  missing_skills: string[]
  experience_alignment: string
  weak_bullets_detected: string[]
  improved_bullet_examples: string[]
  ats_keywords_to_add: string[]
  overall_feedback: string
  improvement_priority: ImprovementPriority[]
}

export interface ParsedResume {
  name: string | null
  email: string | null
  linkedin: string | null
  phone: string | null
  skills: string[]
  education: any[]
  experience: any[]
  projects: any[]
  certifications: any[]
}

export interface ColdEmailRequest {
  companyName: string
  recruiterName: string
  position: string
  userBackground: string
}

export interface ColdEmailResponse {
  subject: string
  body: string
}

export class GeminiService {
  static async generateText(request: GeminiRequest): Promise<GeminiResponse> {
    try {
      const response = await APIClient.post<GeminiResponse>('/gemini/generate', request)
      return response
    } catch (error) {
      console.error('Error generating text with Gemini:', error)
      throw error
    }
  }

  static async analyzeResume(
    request: ResumeAnalysisRequest
  ): Promise<ResumeAnalysisResponse> {
    try {
      const response = await APIClient.post<ResumeAnalysisResponse>(
        '/ai/analyze',
        { job_description: request.jobDescription, resume_text: request.resumeText }
      )

      return response
    } catch (error) {
      console.error('Error analyzing resume:', error)
      throw error
    }
  }

  static async parseResume(resumeText: string): Promise<ParsedResume> {
    try {
      const response = await APIClient.post<ParsedResume>('/ai/parse_resume', {
        resume_text: resumeText,
      })
      return response
    } catch (error) {
      console.error('Error parsing resume:', error)
      throw error
    }
  }
  static async generateColdEmail(request: ColdEmailRequest): Promise<ColdEmailResponse> {
    try {
      // Map frontend request to backend expected format
      // Backend expects: { job_description: str, recruiter_email?: str, role?: str }
      // Frontend provides: { companyName, recruiterName, position, userBackground }

      const payload = {
        job_description: `Company: ${request.companyName}\nUser Background: ${request.userBackground}`,
        role: request.position
      }

      const response = await APIClient.post<any>(
        '/automation/send-cold-email',
        payload
      )

      // Backend returns { message, body }
      return {
        subject: `Application for ${request.position} at ${request.companyName}`, // Backend doesn't return subject, generate a default
        body: response.body
      }
    } catch (error) {
      console.error('Error generating cold email:', error)
      throw error
    }
  }

  static async getInterviewTips(position: string): Promise<string[]> {
    try {
      const response = await APIClient.post<{ tips: string[] }>(
        '/ai/interview-tips',
        { position }
      )
      return response.tips
    } catch (error) {
      console.error('Error getting interview tips:', error)
      throw error
    }
  }

  static async getApplicationInsights(applicationIds: string[]): Promise<Record<string, string>> {
    try {
      const response = await APIClient.post<Record<string, string>>(
        '/gemini/insights',
        { applicationIds }
      )
      return response
    } catch (error) {
      console.error('Error getting application insights:', error)
      throw error
    }
  }
}
