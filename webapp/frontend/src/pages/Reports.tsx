import { useEffect, useState } from 'react'
import { apiService, Report } from '../services/api'
import { Filter, Download, Eye, ExternalLink, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import toast from 'react-hot-toast'

export default function Reports() {
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [totalPages, setTotalPages] = useState(1)
  const [totalRecords, setTotalRecords] = useState(0)
  const [filters, setFilters] = useState({
    application: '',
    riskLevel: '',
    technology: '',
    category: '',
    pwnedOnly: false,
  })
  const [sortBy, setSortBy] = useState<string>('')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [showFilters, setShowFilters] = useState(false)

  useEffect(() => {
    loadReports()
  }, [page, pageSize, filters, sortBy, sortOrder])

  const loadReports = async () => {
    try {
      setLoading(true)
      // Let backend auto-detect the latest database
      const data = await apiService.getReports(page, pageSize, filters, sortBy, sortOrder)
      setReports(data.reports)
      setTotalPages(data.pagination.total_pages)
      setTotalRecords(data.pagination.total)
    } catch (error: any) {
      console.error('Error loading reports:', error)
      toast.error('Error loading reports')
    } finally {
      setLoading(false)
    }
  }

  const handleSort = (column: string) => {
    const newOrder = sortBy === column ? (sortOrder === 'asc' ? 'desc' : 'asc') : 'asc'
    
    if (sortBy === column) {
      // Toggle sort order
      setSortOrder(newOrder)
    } else {
      // New column, default to ascending
      setSortBy(column)
      setSortOrder('asc')
    }
    
    // Reset to first page when sorting changes
    setPage(1)
    
    // Show toast feedback
    const columnNames: Record<string, string> = {
      'url': 'URL',
      'application': 'Aplicación',
      'category': 'Categoría',
      'risk_level': 'Riesgo',
      'is_pwned': 'Estado'
    }
    const orderText = newOrder === 'asc' ? 'ascendente' : 'descendente'
    toast.success(`Ordenando por ${columnNames[column]} (${orderText})`, { duration: 2000 })
  }

  const getSortIcon = (column: string) => {
    if (sortBy !== column) {
      return <ArrowUpDown className="h-4 w-4 opacity-30" />
    }
    return sortOrder === 'asc' 
      ? <ArrowUp className="h-4 w-4 text-primary-400" />
      : <ArrowDown className="h-4 w-4 text-primary-400" />
  }

  const exportToCSV = async () => {
    try {
      setExporting(true)
      toast.loading('Exportando todos los reportes...', { id: 'export' })
      
      // Fetch all reports with current filters and sorting
      const allReports = await apiService.exportReports(filters, sortBy, sortOrder)
      
      const headers = ['URL', 'Application', 'Category', 'Risk Level', 'Pwned', 'Technologies']
      const rows = allReports.map(r => [
        r.url,
        r.application || 'Unknown',
        r.category,
        r.risk_level,
        r.is_pwned ? 'Yes' : 'No',
        r.technologies.join(', ')
      ])
      
      const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `eyewitness-reports-${new Date().toISOString()}.csv`
      a.click()
      
      toast.success(`${allReports.length} reportes exportados exitosamente`, { id: 'export' })
    } catch (error) {
      console.error('Error exporting reports:', error)
      toast.error('Error al exportar reportes', { id: 'export' })
    } finally {
      setExporting(false)
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">Reporte Dinámico</h1>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="px-4 py-2 glass rounded-lg hover:bg-slate-700 transition-colors flex items-center space-x-2"
          >
            <Filter className="h-4 w-4" />
            <span>Filtros</span>
          </button>
          <button
            onClick={exportToCSV}
            disabled={exporting}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download className="h-4 w-4" />
            <span>{exporting ? 'Exportando...' : 'Exportar CSV'}</span>
          </button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="glass rounded-xl p-6">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div>
              <label className="block text-sm text-slate-300 mb-2">Aplicación</label>
              <input
                type="text"
                value={filters.application}
                onChange={(e) => {
                  setFilters({ ...filters, application: e.target.value })
                  setPage(1) // Reset to first page
                }}
                placeholder="Filtrar por aplicación..."
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-300 mb-2">Categoría</label>
              <input
                type="text"
                value={filters.category}
                onChange={(e) => {
                  setFilters({ ...filters, category: e.target.value })
                  setPage(1) // Reset to first page
                }}
                placeholder="Filtrar por categoría..."
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-300 mb-2">Nivel de Riesgo</label>
              <select
                value={filters.riskLevel}
                onChange={(e) => {
                  setFilters({ ...filters, riskLevel: e.target.value })
                  setPage(1) // Reset to first page
                }}
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
                onChange={(e) => {
                  setFilters({ ...filters, technology: e.target.value })
                  setPage(1) // Reset to first page
                }}
                placeholder="Filtrar por tecnología..."
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div className="flex items-end">
              <label className="flex items-center space-x-2 text-slate-300">
                <input
                  type="checkbox"
                  checked={filters.pwnedOnly}
                  onChange={(e) => {
                    setFilters({ ...filters, pwnedOnly: e.target.checked })
                    setPage(1) // Reset to first page
                  }}
                  className="w-4 h-4 text-primary-600 bg-slate-800 border-slate-700 rounded focus:ring-primary-500"
                />
                <span>Solo Pwned</span>
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Reports Table */}
      <div className="glass rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-96">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-800">
                <tr>
                  <th 
                    className={`text-left py-3 px-4 cursor-pointer hover:bg-slate-700 transition-colors ${sortBy === 'url' ? 'text-primary-400 bg-slate-750' : 'text-slate-300'}`}
                    onClick={() => handleSort('url')}
                  >
                    <div className="flex items-center space-x-2">
                      <span>URL</span>
                      {getSortIcon('url')}
                    </div>
                  </th>
                  <th 
                    className={`text-left py-3 px-4 cursor-pointer hover:bg-slate-700 transition-colors ${sortBy === 'application' ? 'text-primary-400 bg-slate-750' : 'text-slate-300'}`}
                    onClick={() => handleSort('application')}
                  >
                    <div className="flex items-center space-x-2">
                      <span>Aplicación</span>
                      {getSortIcon('application')}
                    </div>
                  </th>
                  <th 
                    className={`text-left py-3 px-4 cursor-pointer hover:bg-slate-700 transition-colors ${sortBy === 'category' ? 'text-primary-400 bg-slate-750' : 'text-slate-300'}`}
                    onClick={() => handleSort('category')}
                  >
                    <div className="flex items-center space-x-2">
                      <span>Categoría</span>
                      {getSortIcon('category')}
                    </div>
                  </th>
                  <th 
                    className={`text-left py-3 px-4 cursor-pointer hover:bg-slate-700 transition-colors ${sortBy === 'risk_level' ? 'text-primary-400 bg-slate-750' : 'text-slate-300'}`}
                    onClick={() => handleSort('risk_level')}
                  >
                    <div className="flex items-center space-x-2">
                      <span>Riesgo</span>
                      {getSortIcon('risk_level')}
                    </div>
                  </th>
                  <th 
                    className={`text-left py-3 px-4 cursor-pointer hover:bg-slate-700 transition-colors ${sortBy === 'is_pwned' ? 'text-primary-400 bg-slate-750' : 'text-slate-300'}`}
                    onClick={() => handleSort('is_pwned')}
                  >
                    <div className="flex items-center space-x-2">
                      <span>Estado</span>
                      {getSortIcon('is_pwned')}
                    </div>
                  </th>
                  <th className="text-left py-3 px-4 text-slate-300">Tecnologías</th>
                  <th className="text-left py-3 px-4 text-slate-300">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => (
                  <tr key={report.id} className="border-b border-slate-800 hover:bg-slate-800/50">
                    <td className="py-3 px-4">
                      <a
                        href={report.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary-400 hover:text-primary-300 flex items-center space-x-1"
                      >
                        <span className="truncate max-w-xs">{report.url}</span>
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </td>
                    <td className="py-3 px-4 text-white">
                      <div className="flex items-center gap-2">
                        {report.application || 'Unknown'}
                        {report.http_auth_type && (
                          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-orange-500/20 text-orange-400 border border-orange-500/50">
                            {report.http_auth_type.includes('NTLM') ? 'NTLM' : 
                             report.http_auth_type.includes('Negotiate') ? 'Kerberos' :
                             report.http_auth_type.includes('Basic') ? 'Basic' :
                             'Auth'}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-400">{report.category}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded text-xs font-semibold border ${getRiskBadgeColor(report.risk_level)}`}>
                        {report.risk_level.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {report.is_pwned ? (
                        <span className="px-2 py-1 rounded text-xs font-semibold bg-red-500/20 text-red-400 border border-red-500/50">
                          PWNED
                        </span>
                      ) : (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1">
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
                    </td>
                    <td className="py-3 px-4">
                      {report.screenshot_path && (
                        <button
                          onClick={() => {
                            // Open screenshot in modal or new tab
                            window.open(apiService.getScreenshotUrl(report.id.toString(), report.url), '_blank')
                          }}
                          className="text-primary-400 hover:text-primary-300"
                        >
                          <Eye className="h-5 w-5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="bg-slate-800 px-4 py-3 flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center space-x-4">
            <div className="text-slate-400 text-sm">
              Mostrando {((page - 1) * pageSize) + 1} - {Math.min(page * pageSize, totalRecords)} de {totalRecords}
            </div>
            <div className="flex items-center space-x-2">
              <label className="text-slate-400 text-sm">Por página:</label>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value))
                  setPage(1) // Reset to first page
                }}
                className="px-3 py-1 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="25">25</option>
                <option value="50">50</option>
                <option value="100">100</option>
                <option value="200">200</option>
                <option value="500">500</option>
              </select>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-slate-400 text-sm">
              Página {page} de {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="px-4 py-2 glass rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Anterior
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page === totalPages}
              className="px-4 py-2 glass rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Siguiente
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

