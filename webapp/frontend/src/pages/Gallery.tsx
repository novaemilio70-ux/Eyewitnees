import { useEffect, useState } from 'react'
import { apiService, Report } from '../services/api'
import { Search, Filter, Eye, ExternalLink, X } from 'lucide-react'
import toast from 'react-hot-toast'

export default function Gallery() {
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    application: '',
    riskLevel: '',
    technology: '',
    pwnedOnly: false,
    search: '',
  })
  const [selectedImage, setSelectedImage] = useState<string | null>(null)
  const [showFilters, setShowFilters] = useState(false)

  useEffect(() => {
    loadReports()
  }, [filters])

  const loadReports = async () => {
    try {
      setLoading(true)
      const data = await apiService.getReports(1, 500, filters)
      setReports(data.reports)
    } catch (error: any) {
      console.error('Error loading reports:', error)
      toast.error('Error loading gallery')
    } finally {
      setLoading(false)
    }
  }

  const getRiskBadgeColor = (risk: string) => {
    switch (risk) {
      case 'critical':
        return 'bg-red-500/20 text-red-400 border-red-500/50'
      case 'medium':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50'
      default:
        return 'bg-green-500/20 text-green-400 border-green-500/50'
    }
  }

  const filteredReports = reports.filter((report) => {
    if (filters.search) {
      const searchLower = filters.search.toLowerCase()
      if (
        !report.url.toLowerCase().includes(searchLower) &&
        !(report.application || '').toLowerCase().includes(searchLower) &&
        !report.title.toLowerCase().includes(searchLower)
      ) {
        return false
      }
    }
    return true
  })

  // Show all reports, backend will handle screenshot availability
  const reportsWithScreenshots = filteredReports

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">Galería de Screenshots</h1>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="px-4 py-2 glass rounded-lg hover:bg-slate-700 transition-colors flex items-center space-x-2"
          >
            <Filter className="h-4 w-4" />
            <span>Filtros</span>
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="glass rounded-xl p-6">
        <div className="flex items-center space-x-4 mb-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input
              type="text"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              placeholder="Buscar por URL, aplicación o título..."
              className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        {showFilters && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-4 border-t border-slate-700">
            <div>
              <label className="block text-sm text-slate-300 mb-2">Aplicación</label>
              <input
                type="text"
                value={filters.application}
                onChange={(e) => setFilters({ ...filters, application: e.target.value })}
                placeholder="Filtrar por aplicación..."
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-300 mb-2">Nivel de Riesgo</label>
              <select
                value={filters.riskLevel}
                onChange={(e) => setFilters({ ...filters, riskLevel: e.target.value })}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">Todos</option>
                <option value="critical">Crítico</option>
                <option value="medium">Medio</option>
                <option value="low">Bajo</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-300 mb-2">Tecnología</label>
              <input
                type="text"
                value={filters.technology}
                onChange={(e) => setFilters({ ...filters, technology: e.target.value })}
                placeholder="Filtrar por tecnología..."
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div className="flex items-end">
              <label className="flex items-center space-x-2 text-slate-300">
                <input
                  type="checkbox"
                  checked={filters.pwnedOnly}
                  onChange={(e) => setFilters({ ...filters, pwnedOnly: e.target.checked })}
                  className="w-4 h-4 text-primary-600 bg-slate-800 border-slate-700 rounded focus:ring-primary-500"
                />
                <span>Solo Pwned</span>
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Gallery Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
        </div>
      ) : reportsWithScreenshots.length === 0 ? (
        <div className="text-center py-12 glass rounded-xl">
          <p className="text-slate-400">No hay screenshots disponibles</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {reportsWithScreenshots.map((report) => (
            <div
              key={report.id}
              className="glass rounded-xl overflow-hidden hover:scale-105 transition-transform cursor-pointer"
              onClick={() => {
                const screenshotUrl = apiService.getScreenshotUrl(
                  report.id.toString(),
                  report.url
                )
                setSelectedImage(screenshotUrl)
              }}
            >
              {/* Screenshot Thumbnail */}
              <div className="relative aspect-video bg-slate-800">
                <img
                  src={apiService.getScreenshotUrl(report.id.toString(), report.url)}
                  alt={report.title}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement
                    // Show different placeholder for HTTP Authentication pages
                    if (report.http_auth_type) {
                      const authType = report.http_auth_type.includes('NTLM') ? 'NTLM Authentication' :
                                      report.http_auth_type.includes('Negotiate') ? 'Kerberos/NTLM' :
                                      report.http_auth_type.includes('Basic') ? 'Basic Auth' :
                                      report.http_auth_type.includes('Digest') ? 'Digest Auth' :
                                      'HTTP Authentication'
                      // Windows-style login dialog placeholder
                      target.src = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300'%3E%3Cdefs%3E%3ClinearGradient id='bg' x1='0%25' y1='0%25' x2='0%25' y2='100%25'%3E%3Cstop offset='0%25' stop-color='%23334155'/%3E%3Cstop offset='100%25' stop-color='%231e293b'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect fill='url(%23bg)' width='400' height='300'/%3E%3Crect x='50' y='40' width='300' height='220' rx='8' fill='%23475569' stroke='%23f97316' stroke-width='2'/%3E%3Crect x='50' y='40' width='300' height='35' rx='8' fill='%23f97316'/%3E%3Ctext fill='white' x='200' y='64' text-anchor='middle' font-family='Arial' font-size='14' font-weight='bold'%3E${encodeURIComponent(authType)}%3C/text%3E%3Ctext fill='%2394a3b8' x='200' y='100' text-anchor='middle' font-family='Arial' font-size='11'%3EWindows Security%3C/text%3E%3Crect x='80' y='120' width='240' height='28' rx='4' fill='%231e293b' stroke='%23475569'/%3E%3Ctext fill='%2364748b' x='95' y='139' font-family='Arial' font-size='12'%3EUsername%3C/text%3E%3Crect x='80' y='160' width='240' height='28' rx='4' fill='%231e293b' stroke='%23475569'/%3E%3Ctext fill='%2364748b' x='95' y='179' font-family='Arial' font-size='12'%3EPassword%3C/text%3E%3Crect x='180' y='210' width='60' height='28' rx='4' fill='%233b82f6'/%3E%3Ctext fill='white' x='210' y='229' text-anchor='middle' font-family='Arial' font-size='11'%3EOK%3C/text%3E%3Crect x='250' y='210' width='60' height='28' rx='4' fill='%23475569'/%3E%3Ctext fill='white' x='280' y='229' text-anchor='middle' font-family='Arial' font-size='11'%3ECancel%3C/text%3E%3C/svg%3E`
                    } else {
                      target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="300"%3E%3Crect fill="%231e293b" width="400" height="300"/%3E%3Ctext fill="%2394a3b8" x="50%25" y="50%25" text-anchor="middle" dy=".3em"%3EImagen no disponible%3C/text%3E%3C/svg%3E'
                    }
                    target.onerror = null // Prevent infinite loop
                  }}
                />
                
                {/* Status Badges - Top Right */}
                <div className="absolute top-2 right-2 flex flex-col gap-1 items-end">
                  {report.is_pwned && (
                    <div className="px-2 py-1 rounded text-xs font-semibold bg-red-500/90 text-white border border-red-500">
                      PWNED
                    </div>
                  )}
                  {report.http_auth_type && (
                    <div className="px-2 py-1 rounded text-xs font-semibold bg-orange-500/90 text-white border border-orange-500">
                      {report.http_auth_type.includes('NTLM') ? 'NTLM' : 
                       report.http_auth_type.includes('Negotiate') ? 'Kerberos' :
                       report.http_auth_type.includes('Basic') ? 'Basic Auth' :
                       'HTTP Auth'}
                    </div>
                  )}
                </div>
                
                {/* Risk Badge */}
                <div className="absolute top-2 left-2">
                  <span className={`px-2 py-1 rounded text-xs font-semibold border ${getRiskBadgeColor(report.risk_level)}`}>
                    {report.risk_level.toUpperCase()}
                  </span>
                </div>
              </div>

              {/* Card Info */}
              <div className="p-4">
                <h3 className="text-white font-semibold mb-1 truncate" title={report.title}>
                  {report.title}
                </h3>
                <p className="text-sm text-slate-400 mb-2 truncate" title={report.url}>
                  {report.url}
                </p>
                
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-slate-300">
                    {report.application || 'Unknown'}
                  </span>
                  {report.category && (
                    <span className="text-xs px-2 py-1 rounded bg-slate-700 text-slate-300">
                      {report.category}
                    </span>
                  )}
                </div>

                {/* Technologies */}
                {report.technologies.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {report.technologies.slice(0, 3).map((tech, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 rounded text-xs bg-slate-700 text-slate-300"
                      >
                        {tech}
                      </span>
                    ))}
                    {report.technologies.length > 3 && (
                      <span className="px-2 py-1 rounded text-xs bg-slate-700 text-slate-300">
                        +{report.technologies.length - 3}
                      </span>
                    )}
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-700">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      window.open(report.url, '_blank')
                    }}
                    className="text-primary-400 hover:text-primary-300 text-sm flex items-center space-x-1"
                  >
                    <ExternalLink className="h-4 w-4" />
                    <span>Abrir URL</span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      const screenshotUrl = apiService.getScreenshotUrl(
                        report.id.toString(),
                        report.url
                      )
                      setSelectedImage(screenshotUrl)
                    }}
                    className="text-primary-400 hover:text-primary-300 text-sm flex items-center space-x-1"
                  >
                    <Eye className="h-4 w-4" />
                    <span>Ver</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Lightbox Modal */}
      {selectedImage && (
        <div
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
          onClick={() => setSelectedImage(null)}
        >
          <button
            onClick={() => setSelectedImage(null)}
            className="absolute top-4 right-4 text-white hover:text-slate-300 z-10"
          >
            <X className="h-8 w-8" />
          </button>
          <img
            src={selectedImage}
            alt="Screenshot"
            className="max-w-full max-h-full object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* Stats Footer */}
      <div className="glass rounded-xl p-4">
        <div className="flex items-center justify-between text-sm text-slate-400">
          <span>
            Mostrando {reportsWithScreenshots.length} de {reports.length} reportes con screenshots
          </span>
          <span>
            {reports.filter((r) => r.is_pwned).length} vulnerabilidades críticas
          </span>
        </div>
      </div>
    </div>
  )
}

