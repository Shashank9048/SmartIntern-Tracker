// User Types
export interface User {
  _id: string
  email: string
  name: string
  createdAt: string
  updatedAt: string
}

export interface AuthResponse {
  user: User
  token: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  name: string
}

// Application Types
export type ApplicationStatus = 'Applied' | 'Interview' | 'Rejected' | 'Selected'

export interface ActionPlanItem {
  priority: 'High' | 'Medium' | 'Low'
  title: string
  description: string
}

export interface ApplicationAnalysis {
  overall_match_score?: number
  match_score?: number
  experience_alignment?: 'High' | 'Medium' | 'Low' | string
  skills_found?: string[]
  missing_skills?: string[]
  strengths?: string[]
  weaknesses?: string[]
  improvement_suggestions?: string[]
  action_plan?: ActionPlanItem[]
  ats_score?: number
  summary?: string
  resume_completeness?: {
    has_summary: boolean
    has_projects: boolean
    has_experience: boolean
    has_skills_section: boolean
    has_education: boolean
  }
  resume_snapshot?: string
  job_description?: string
}

export interface Application {
  _id: string
  user_id: string
  company_name: string
  role: string
  status: ApplicationStatus
  applied_date: string
  interview_date?: string
  deadline_date?: string
  notes?: string
  job_description?: string

  // AI-generated fields
  ai_match_score?: number
  ai_experience_alignment?: string
  ai_summary?: string
  ai_missing_skills?: string[]
  ai_suggestions?: string[]
  analysis?: ApplicationAnalysis

  created_at: string
  updated_at: string
}

export interface ApplicationCreateRequest {
  company_name: string
  role: string
  status: ApplicationStatus
  applied_date: string
  interview_date?: string
  deadline_date?: string
  notes?: string
}

export interface ApplicationUpdateRequest {
  company_name?: string
  role?: string
  status?: ApplicationStatus
  applied_date?: string
  interview_date?: string
  deadline_date?: string
  notes?: string
}

// Resume Types
export interface Resume {
  _id: string
  userId: string
  filename: string
  fileUrl: string
  uploadedAt: string
  isPrimary: boolean
  analysisScore?: number
}

export interface ResumeUploadRequest {
  file: File
  userId: string
}

// Gemini AI Types
export interface ResumeAnalysis {
  matchScore: number
  strengths: string[]
  weaknesses: string[]
  missingKeywords: string[]
  suggestions: string[]
}

export interface ColdEmailGeneration {
  subject: string
  body: string
}

export interface ColdEmailRequest {
  companyName: string
  recruiterName: string
  position: string
  userBackground: string
}

export interface InterviewTips {
  tips: string[]
}

export interface AIInsights {
  [applicationId: string]: string
}

// Automation Types
export type AutomationTrigger = 'application_created' | 'status_changed' | 'reminder' | 'daily'
export type AutomationAction = 'send_email' | 'create_reminder' | 'update_status' | 'send_notification'

export interface AutomationRule {
  _id: string
  userId: string
  name: string
  trigger: AutomationTrigger
  action: AutomationAction
  isEnabled: boolean
  createdAt?: string
  updatedAt?: string
}

export interface AutomationRuleCreateRequest {
  name: string
  trigger: AutomationTrigger
  action: AutomationAction
}

// Analytics Types
export interface ApplicationStats {
  total: number
  applied: number
  interviewing: number
  rejected: number
  offers: number
  accepted?: number
}

export interface DashboardMetrics {
  stats: ApplicationStats
  recentApplications: Application[]
  applicationsByMonth: Array<{ month: string; count: number }>
  statusBreakdown: Record<ApplicationStatus, number>
}

// API Response Types
export interface APIResponse<T> {
  data: T
  message?: string
  error?: string
}

export interface APIError {
  message: string
  code?: string
  details?: Record<string, unknown>
}

// Filter & Search Types
export interface ApplicationFilters {
  status?: ApplicationStatus
  companyName?: string
  position?: string
  dateRange?: {
    start: string
    end: string
  }
  matchScoreMin?: number
  sortBy?: 'date' | 'company' | 'matchScore' | 'status'
  sortOrder?: 'asc' | 'desc'
}

// Chat Types
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export interface ChatSession {
  id: string
  userId: string
  messages: ChatMessage[]
  createdAt: Date
  updatedAt: Date
}

// Settings Types
export interface UserSettings {
  emailNotifications: boolean
  interviewReminders: boolean
  applicationUpdates: boolean
  theme: 'light' | 'dark' | 'system'
  language: string
}

export interface NotificationSettings {
  userId: string
  emailNotifications: boolean
  pushNotifications: boolean
  smsNotifications: boolean
  reminderDaysBeforeInterview: number
  applicationReminder: boolean
}

// Pagination Types
export interface PaginationParams {
  page: number
  limit: number
  offset?: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  hasMore: boolean
}

// Form Types
export interface FormState {
  isSubmitting: boolean
  error?: string
  success?: string
}

export interface FormErrors {
  [key: string]: string
}

// Phase 5 â€” Job Matching Feed Types

export type MatchStatus = 'no_resume' | 'computing' | 'ready'

export interface RecommendedJobEntry {
  job_id: string
  match_score: number
  matched_skills: string[]
  missing_skills: string[]
  job: {
    title: string
    company: string
    location: string
    description: string
    required_skills: string[]
    posted_at?: string
  }
}

export interface MatchStatusResponse {
  status: MatchStatus
  match_count: number
  resume_version?: string
}


// Phase 6B — Tracked Jobs (feed-sourced kanban)

export type TrackedJobStatus =
  | 'wishlist'
  | 'applied'
  | 'oa'
  | 'interview'
  | 'offer'
  | 'rejected'

export interface TrackedJobEntry {
  _id: string
  status: TrackedJobStatus
  match_score_at_save: number
  applied_at: string
  updated_at: string
  job: {
    title: string
    company: string
    location: string
  }
  job_id: string
}

// Phase 7 - Notifications

export type NotificationType = 'digest' | 'deadline' | 'interview'

export interface AppNotification {
  id: string
  type: NotificationType
  payload: Record<string, any>
  read_bool: boolean
  created_at: string
}
