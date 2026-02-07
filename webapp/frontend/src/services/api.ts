import axios from 'axios'

// Use relative URLs in development (Vite proxy handles it) or explicit URL in production
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

console.log('[API] Base URL:', API_BASE_URL || '(using proxy)')

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    console.log('[API] Request:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('[API] Request error:', error)
    return Promise.reject(error)
  }
)

// Add response interceptor for debugging
api.interceptors.response.use(
  (response) => {
    console.log('[API] Response:', response.status, response.config.url)
    return response
  },
  (error) => {
    console.error('[API] Response error:', error.message, error.config?.url)
    return Promise.reject(error)
  }
)

export interface DashboardStats {
  stats: {
    total_scans: number
    critical_vulnerabilities: number
    applications_detected: number
    credentials_found: number
    credentials_tested: number
  }
  top_vulnerable_apps: Array<{
    name: string
    vulnerabilities: number
  }>
  tech_risk_map: Record<string, {
    total: number
    vulnerable: number
  }>
  category_risk_map: Record<string, {
    total: number
    vulnerable: number
  }>
  vulnerabilities_by_day: Record<string, number>
}

export interface Report {
  id: number
  url: string
  title: string
  category: string
  application: string | null
  technologies: string[]
  has_credentials: boolean
  is_pwned: boolean
  working_credentials: string[]
  screenshot_path: string | null
  timestamp: string
  risk_level: 'low' | 'medium' | 'critical'
  http_auth_type?: string | null  // NTLM, Basic, Digest, Negotiate, etc.
}

export interface ReportsResponse {
  reports: Report[]
  pagination: {
    page: number
    page_size: number
    total: number
    total_pages: number
  }
}

export interface PasswordAnalysis {
  vulnerable_credentials: Array<{
    url: string
    application: string
    username: string
    password: string
    category: string
  }>
  application_statistics: Array<{
    application: string
    total_tested: number
    successful: number
    success_rate: number
  }>
  total_vulnerable: number
  recommendations: string[]
}

export interface AIAnalysis {
  detected_applications: Array<{
    name: string
    count: number
    confidence: string
    technologies: string[]
    vulnerable: boolean
  }>
  technology_timeline: Array<{
    technology: string
    timestamp: string
    url: string
  }>
  confidence_metrics: {
    high: number
    medium: number
    low: number
  }
  total_detections: number
}

export interface Project {
  name: string
  db_path: string
  last_modified: string
  size_bytes: number
  size_mb: number
  is_current?: boolean
  is_default?: boolean
}

export interface ProjectsResponse {
  projects: Project[]
  current_project: string | null
  total: number
  env_project: string | null
}

export const apiService = {
  async getProjects(): Promise<ProjectsResponse> {
    const response = await api.get('/api/projects')
    return response.data
  },

  async loadProject(projectName: string) {
    const response = await api.post('/api/load-project', null, {
      params: { project_name: projectName },
    })
    return response.data
  },

  async loadDatabase(dbPath: string) {
    const response = await api.post('/api/load-database', null, {
      params: { db_path: dbPath },
    })
    return response.data
  },

  async getDashboardStats(dbPath?: string): Promise<DashboardStats> {
    const response = await api.get('/api/dashboard', {
      params: dbPath ? { db_path: dbPath } : {},
    })
    return response.data
  },

  async getReports(
    page: number = 1,
    pageSize: number = 50,
    filters?: {
      application?: string
      riskLevel?: string
      technology?: string
      category?: string
      pwnedOnly?: boolean
    },
    sortBy?: string,
    sortOrder?: 'asc' | 'desc',
    dbPath?: string
  ): Promise<ReportsResponse> {
    const params: any = {
      page,
      page_size: pageSize,
    }
    if (filters?.application) params.application = filters.application
    if (filters?.riskLevel) params.risk_level = filters.riskLevel
    if (filters?.technology) params.technology = filters.technology
    if (filters?.category) params.category = filters.category
    if (filters?.pwnedOnly) params.pwned_only = filters.pwnedOnly
    if (sortBy && sortBy.trim() !== '') {
      params.sort_by = sortBy
      params.sort_order = sortOrder || 'asc'
    }
    if (dbPath) params.db_path = dbPath

    const response = await api.get('/api/reports', { params })
    return response.data
  },

  async exportReports(
    filters?: {
      application?: string
      riskLevel?: string
      technology?: string
      category?: string
      pwnedOnly?: boolean
    },
    sortBy?: string,
    sortOrder?: 'asc' | 'desc',
    dbPath?: string
  ): Promise<Report[]> {
    const params: any = {}
    if (filters?.application) params.application = filters.application
    if (filters?.riskLevel) params.risk_level = filters.riskLevel
    if (filters?.technology) params.technology = filters.technology
    if (filters?.category) params.category = filters.category
    if (filters?.pwnedOnly) params.pwned_only = filters.pwnedOnly
    if (sortBy && sortBy.trim() !== '') {
      params.sort_by = sortBy
      params.sort_order = sortOrder || 'asc'
    }
    if (dbPath) params.db_path = dbPath

    const response = await api.get('/api/reports/export', { params })
    return response.data.reports
  },

  async getPasswordAnalysis(dbPath?: string): Promise<PasswordAnalysis> {
    const response = await api.get('/api/passwords', {
      params: dbPath ? { db_path: dbPath } : {},
    })
    return response.data
  },

  async getAIAnalysis(dbPath?: string): Promise<AIAnalysis> {
    const response = await api.get('/api/ai-analysis', {
      params: dbPath ? { db_path: dbPath } : {},
    })
    return response.data
  },

  getScreenshotUrl(scanId: string, urlHash: string): string {
    // Encode the URL hash to handle special characters
    const encodedHash = encodeURIComponent(urlHash)
    // Use absolute URL for screenshots (they need direct access)
    const baseUrl = API_BASE_URL || 'http://localhost:5000'
    return `${baseUrl}/api/screenshot/${scanId}/${encodedHash}`
  },
}

export default api

