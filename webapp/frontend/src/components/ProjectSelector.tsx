import { useEffect, useState } from 'react'
import { apiService, Project } from '../services/api'
import { Database, ChevronDown, Check } from 'lucide-react'
import toast from 'react-hot-toast'

export default function ProjectSelector() {
  const [projects, setProjects] = useState<Project[]>([])
  const [currentProject, setCurrentProject] = useState<string | null>(null)
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    try {
      setLoading(true)
      const data = await apiService.getProjects()
      setProjects(data.projects)
      setCurrentProject(data.current_project)
    } catch (error: any) {
      console.error('Error loading projects:', error)
      toast.error('Error loading projects')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectProject = async (projectName: string) => {
    try {
      await apiService.loadProject(projectName)
      setCurrentProject(projectName)
      setIsOpen(false)
      toast.success(`Project "${projectName}" loaded successfully`)
      // Reload the page to refresh all data
      window.location.reload()
    } catch (error: any) {
      console.error('Error loading project:', error)
      toast.error(`Error loading project: ${error.response?.data?.detail || error.message}`)
    }
  }

  const currentProjectData = projects.find(p => p.name === currentProject) || 
                            projects.find(p => p.is_default) ||
                            projects[0]

  if (loading) {
    return (
      <div className="flex items-center space-x-2 text-slate-300">
        <Database className="h-5 w-5 animate-pulse" />
        <span className="text-sm">Loading projects...</span>
      </div>
    )
  }

  if (projects.length === 0) {
    return (
      <div className="flex items-center space-x-2 text-slate-400">
        <Database className="h-5 w-5" />
        <span className="text-sm">No projects found</span>
      </div>
    )
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors text-white"
      >
        <Database className="h-5 w-5" />
        <span className="text-sm font-medium">
          {currentProjectData?.name || 'Select Project'}
        </span>
        <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 mt-2 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-20 max-h-96 overflow-y-auto">
            <div className="p-2">
              <div className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Available Projects ({projects.length})
              </div>
              {projects.map((project) => (
                <button
                  key={project.name}
                  onClick={() => handleSelectProject(project.name)}
                  className={`w-full text-left px-3 py-2 rounded-md transition-colors flex items-center justify-between ${
                    project.name === currentProject
                      ? 'bg-primary-600 text-white'
                      : 'text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{project.name}</div>
                    <div className="text-xs opacity-75">
                      {project.size_mb} MB • {new Date(project.last_modified).toLocaleDateString()}
                    </div>
                  </div>
                  {project.name === currentProject && (
                    <Check className="h-4 w-4 ml-2 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

