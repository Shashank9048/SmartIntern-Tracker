# Complete Setup Guide - Smart Internship Tracker

## Overview

This is a fully functional AI-powered internship tracking application with:
- User authentication (Email/Password + Google OAuth)
- Application management (CRUD operations)
- Resume analysis with Gemini AI
- Cold email generation with Gemini AI
- AI career assistant chatbot
- Automation and reminders
- Dashboard with analytics

## Prerequisites

1. Your backend deployed at: `https://smartinternbackend.vercel.app/`
2. MongoDB database connected to your backend
3. Gemini API key configured on your backend
4. Google OAuth credentials (optional, for social login)

## Frontend Environment Variables

Add these to your Vercel project or `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=https://smartinternbackend.vercel.app
NEXT_PUBLIC_GEMINI_API_KEY=your_gemini_api_key_here
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_google_client_id_here (optional)
```

## Features Overview

### 1. Authentication Pages

**Login Page** (`/login`)
- Email/Password login
- Google OAuth login (if configured)
- Form validation
- Error handling with toast notifications

**Signup Page** (`/signup`)
- Email/Password registration
- Student profile (name, branch, graduation year)
- Resume upload (PDF/DOC/DOCX)
- Skills input
- Google OAuth signup (if configured)

### 2. Dashboard (`/dashboard`)
- Overview of applications
- Statistics cards (total, interviews, offers)
- Application status breakdown (pie chart)
- Timeline of applications (bar chart)
- AI insights about your applications

### 3. Applications Page (`/applications`)
- View all applications in grid or list view
- Search and filter applications
- Add new applications with modal
- Edit application details
- Delete applications
- Track match score and status
- Color-coded status badges

### 4. Resume Manager (`/resume`)
- Drag-and-drop resume upload
- Resume analyzer with Gemini AI
- Job description matching
- Keywords analysis
- Missing skills identification
- Improvement suggestions

### 5. AI Assistant (`/assistant`)
- Chat interface with Gemini AI
- Interview preparation help
- Career advice
- Real-time responses
- Chat history in session

### 6. Cold Email Generator (`/cold-email`)
- Generate personalized cold emails
- Recruiter name, company, position inputs
- Skills and interests customization
- One-click copy to clipboard
- Regenerate emails

### 7. Automation & Reminders (`/automation`)
- Interview reminder settings
- Upcoming interviews list
- Status change notifications
- Interview preparation checklist
- Follow-up reminders (7 & 14 days)

### 8. Settings (`/settings`)
- User profile management
- Password change
- Resume management
- Theme switching (light/dark)
- Notification preferences
- Account deletion

## Backend Integration

All API calls are made through the APIClient utility at `/lib/api-client.ts`.

### Key Features:
- Automatic JWT token management
- Bearer token authentication
- Error handling and fallbacks
- Network error detection

### Making API Calls:

```typescript
import { APIClient } from '@/lib/api-client'

// GET request
const data = await APIClient.get('/applications')

// POST request
const result = await APIClient.post('/applications', {
  company: 'Google',
  position: 'Engineer'
})

// PUT request
const updated = await APIClient.put('/applications/id', {
  status: 'interviewed'
})

// DELETE request
await APIClient.delete('/applications/id')
```

## Gemini Integration

AI features use the GeminiService at `/lib/gemini-service.ts`:

```typescript
import { GeminiService } from '@/lib/gemini-service'

// Generate text
const response = await GeminiService.generateText({
  prompt: 'Your question here',
  context: 'System context'
})

// Analyze resume
const analysis = await GeminiService.analyzeResume({
  resumeText: 'Resume content',
  jobDescription: 'Job description'
})

// Generate cold email
const email = await GeminiService.generateColdEmail({
  recruiterName: 'John',
  companyName: 'Google',
  position: 'Engineer',
  skills: 'Python, React',
  interest: 'Innovation'
})

// Get interview tips
const tips = await GeminiService.getInterviewTips('Software Engineer')

// Get insights
const insights = await GeminiService.getApplicationInsights(['app_id_1', 'app_id_2'])
```

## File Structure

```
app/
├── login/               # Login page
├── signup/              # Signup page
├── dashboard/           # Dashboard page
├── applications/        # Applications management
├── resume/              # Resume manager
├── assistant/           # AI assistant
├── cold-email/          # Cold email generator
├── automation/          # Automation & reminders
├── settings/            # Settings page
└── page.tsx             # Root redirects to /login

components/
├── app-layout.tsx       # Layout wrapper
├── navbar.tsx           # Top navigation
├── sidebar.tsx          # Side navigation
├── theme-provider.tsx   # Theme management
├── applications/        # Application components
├── assistant/           # AI assistant components
├── dashboard/           # Dashboard components
├── resume/              # Resume components
└── ui/                  # shadcn/ui components

lib/
├── api-client.ts        # API utility
├── gemini-service.ts    # Gemini AI service
└── mongodb-service.ts   # MongoDB operations

context/
└── auth-context.tsx     # Authentication context

hooks/
├── use-applications.ts  # Applications hook
└── use-resumes.ts       # Resume hook

types/
└── index.ts             # TypeScript types
```

## Troubleshooting

### Authentication Issues
- Check that your backend `/auth/login` and `/auth/register` endpoints are working
- Verify JWT tokens are being returned correctly
- Check CORS settings on your backend

### API Calls Failing
- Verify `NEXT_PUBLIC_API_BASE_URL` is correct
- Check that Authorization header is being sent
- Look at network tab in browser DevTools
- Check backend logs for error messages

### Gemini AI Not Working
- Verify `NEXT_PUBLIC_GEMINI_API_KEY` is set
- Check your Gemini API quota
- Review Gemini service error logs

### Google OAuth Not Working
- Verify `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is correct
- Check that your frontend domain is authorized in Google Console
- Ensure Google Sign-In script is loading

## Deployment

### To Vercel:
1. Connect your GitHub repo
2. Set environment variables in Vercel dashboard
3. Deploy

### To Other Platforms:
1. Build: `npm run build`
2. Start: `npm run start`
3. Set environment variables on your platform

## Testing

1. Test authentication flow (login/signup)
2. Test application CRUD operations
3. Test resume upload and analysis
4. Test cold email generation
5. Test AI assistant chat
6. Test automation reminders
7. Test profile settings

## Performance Tips

- Resume uploads are validated client-side (5MB max)
- API calls have proper error handling and fallbacks
- Images are optimized and lazy-loaded
- Dark mode is the default for better performance

## Support

For issues:
1. Check this guide and BACKEND_ENDPOINTS_REQUIRED.md
2. Check browser console for errors
3. Check network tab for API failures
4. Check backend logs for server errors
5. Verify all environment variables are set correctly
