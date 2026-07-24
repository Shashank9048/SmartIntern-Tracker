export const API_URL = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const BASE_URL = API_URL;

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface SignupResponse {
  access_token: string;
  token_type: string;
}

export const loginUser = async (email: string, password: string): Promise<LoginResponse> => {
  const response = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const errorData = await handleApiError(response, 'Login');
    throw new Error(errorData.detail || 'Invalid email or password');
  }
  return response.json();
};

export const signupUser = async (
  email: string,
  password: string,
  full_name: string,
  branch?: string,
  graduation_year?: string,
  skills?: string[]
): Promise<SignupResponse> => {
  try {
    const payload = { email, password, full_name, branch, graduation_year, skills: skills || [] };
    const response = await fetch(`${BASE_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errorData = await handleApiError(response, 'Signup');
      throw new Error(errorData.detail || 'Signup failed');
    }
    return await response.json();
  } catch (error) {
    console.error('Signup error:', error);
    throw error;
  }
};

// --- Internals ---

const handleApiError = async (response: Response, context: string) => {
  const text = await response.text();
  // Use warn instead of error to avoid spurious red console noise for expected API failures
  console.warn(`${context} failed (${response.status}):`, text.substring(0, 200));
  try {
    return JSON.parse(text);
  } catch {
    return { detail: `${context} failed` };
  }
}

const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
  };
};

// --- Applications ---

export const getApplications = async (): Promise<any[]> => {
  const response = await fetch(`${BASE_URL}/api/applications`, { headers: getAuthHeaders() });
  if (!response.ok) throw new Error('Failed to fetch applications');
  return response.json();
};

// --- Resume ---

export const getLatestAnalysis = async (): Promise<any> => {
  try {
    const response = await fetch(`${BASE_URL}/ai/latest-analysis`, { headers: getAuthHeaders() });
    if (response.status === 404) return null; // No analysis yet — graceful
    if (!response.ok) throw new Error('Failed to fetch latest analysis');
    return response.json();
  } catch (error) {
    console.error('Latest Analysis error:', error);
    return null;
  }
};

export const parseResume = async (resumeText: string): Promise<any> => {
  const response = await fetch(`${BASE_URL}/ai/parse_resume`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ resume_text: resumeText }),
  });
  if (!response.ok) {
    const errorData = await handleApiError(response, 'Parse Resume');
    throw new Error(errorData.detail || 'Failed to parse resume');
  }
  return response.json();
};

export const uploadResume = async (file: File): Promise<any> => {
  const token = localStorage.getItem('access_token');
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${BASE_URL}/api/resume/upload`, {
    method: 'POST',
    headers: {
      // NOTE: Do NOT set Content-Type here — browser sets it automatically with boundary for multipart
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: formData,
  });
  if (!response.ok) {
    const errorData = await handleApiError(response, 'Upload Resume');
    throw new Error(errorData.detail || 'Failed to upload resume');
  }
  return response.json();
};

export const uploadAvatar = async (file: File): Promise<{ profile_picture_url: string }> => {
  const token = localStorage.getItem('access_token');
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${BASE_URL}/user/upload-avatar`, {
    method: 'POST',
    headers: {
      // Do NOT set Content-Type — browser sets it automatically with multipart boundary
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: formData,
  });
  if (!response.ok) {
    const errorData = await handleApiError(response, 'Upload Avatar');
    throw new Error(errorData.detail || 'Failed to upload avatar');
  }
  return response.json();
};

// --- User Profile ---

export interface UserProfile {
  email: string;
  full_name: string;
  branch?: string;
  graduation_year?: string;
  skills: string[];
  resume_text?: string;
  profile_picture?: string;
  preferences?: {
    theme: string;
    notifications: { email: boolean; interview: boolean; marketing: boolean };
  };
}

export const getUserProfile = async (): Promise<UserProfile> => {
  const response = await fetch(`${BASE_URL}/user/me`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    const text = await response.text();
    console.error('Get Profile failed:', response.status, text.substring(0, 100));
    throw new Error(`Failed to fetch profile (${response.status})`);
  }
  return response.json();
};

export const updateUserProfile = async (data: Partial<UserProfile> & { password?: string }): Promise<UserProfile> => {
  const response = await fetch(`${BASE_URL}/user/me`, {
    method: 'PATCH',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const errorData = await handleApiError(response, 'Update Profile');
    throw new Error(errorData.detail || 'Failed to update profile');
  }
  return response.json();
};

export const changePassword = async (currentPassword: string, newPassword: string): Promise<void> => {
  const response = await fetch(`${BASE_URL}/user/change-password`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!response.ok) {
    const errorData = await handleApiError(response, 'Change Password');
    throw new Error(errorData.detail || 'Failed to change password');
  }
};

// --- AI Dashboard Insights ---

export interface DashboardInsights {
  trends: string;
  improvement_strategy: string;
  follow_up_suggestions: string[];
  learning_roadmap: string;
}

export const getDashboardInsights = async (): Promise<DashboardInsights> => {
  const response = await fetch(`${BASE_URL}/api/insights/dashboard`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    const errorData = await handleApiError(response, 'Dashboard Insights');
    throw new Error(errorData.detail || 'Failed to fetch insights');
  }
  return response.json();
};

// --- Resume Analysis ---

export const analyzeResume = async ({ jobDescription, resumeText }: { jobDescription: string; resumeText?: string }): Promise<any> => {
  const response = await fetch(`${BASE_URL}/api/resume/analyze`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ job_description: jobDescription, resume_text: resumeText }),
  });
  if (!response.ok) {
    const errorData = await handleApiError(response, 'Analyze Resume');
    throw new Error(errorData.detail || 'Failed to analyze resume');
  }
  return response.json();
};

// --- Resume Profile (Phase 2 — Structured Storage) ---

export interface ParsedResumeJson {
  name?: string;
  email?: string;
  linkedin?: string;
  phone?: string;
  skills?: string[];
  education?: string[];
  experience?: string[];
  projects?: string[];
  certifications?: string[];
}

export interface ResumeProfile {
  id: string | null;
  user_id: string;
  status: 'pending' | 'parsed' | 'failed';
  raw_text: string;
  parsed_json: ParsedResumeJson;
  file_url: string | null;
  original_filename: string | null;
  uploaded_at: string | null;
  resume_version: string;
}

/**
 * GET /api/resume/me — returns the user's structured Resume document (Phase 2).
 * Returns null if no resume has been uploaded yet (404 → null).
 */
export const getResumeProfile = async (): Promise<ResumeProfile | null> => {
  try {
    const response = await fetch(`${BASE_URL}/api/resume/me`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
    if (response.status === 404) return null;
    if (!response.ok) {
      const errorData = await handleApiError(response, 'Get Resume Profile');
      throw new Error(errorData.detail || 'Failed to fetch resume profile');
    }
    return response.json();
  } catch (error) {
    console.error('getResumeProfile error:', error);
    return null;
  }
};

/**
 * DELETE /api/resume/me — permanently deletes the user's stored Resume document.
 */
export const deleteResume = async (): Promise<void> => {
  const response = await fetch(`${BASE_URL}/api/resume/me`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!response.ok && response.status !== 204) {
    const errorData = await handleApiError(response, 'Delete Resume');
    throw new Error(errorData.detail || 'Failed to delete resume');
  }
};

// --- AI Chat ---

export const chatWithAI = async (message: string): Promise<string> => {
  const response = await fetch(`${BASE_URL}/ai/chat`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    const errorData = await handleApiError(response, 'AI Chat');
    throw new Error(errorData.detail || 'AI chat failed');
  }
  const data = await response.json();
  return data.reply as string;
};

export const deleteUserProfile = async (): Promise<void> => {
  const response = await fetch(`${BASE_URL}/user/me`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!response.ok && response.status !== 204) {
    const errorData = await handleApiError(response, 'Delete Account');
    throw new Error(errorData.detail || 'Failed to delete account');
  }
};

/**
 * Calls POST /auth/logout — backend ack for JWT logout.
 * Token invalidation is client-side; this just notifies the server.
 */
export const logoutUser = async (): Promise<void> => {
  try {
    const response = await fetch(`${BASE_URL}/auth/logout`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!response.ok) {
      console.warn('Logout endpoint returned non-OK status:', response.status);
    }
  } catch (err) {
    // Silently swallow — if the server is unreachable on logout, that's fine
    console.warn('Logout request failed (ignoring):', err);
  }
};

/**
 * GET /auth/me — spec-compliant alias for getUserProfile.
 * Returns the authenticated user's full profile.
 */
export const getAuthMe = async (): Promise<UserProfile> => {
  const response = await fetch(`${BASE_URL}/auth/me`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    const text = await response.text();
    console.error('Auth/me failed:', response.status, text.substring(0, 100));
    throw new Error(`Failed to fetch auth profile (${response.status})`);
  }
  return response.json();
};
