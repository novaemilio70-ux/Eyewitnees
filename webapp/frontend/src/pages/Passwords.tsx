import { useEffect, useState } from 'react'
import { apiService, PasswordAnalysis } from '../services/api'
import { Shield, AlertTriangle, CheckCircle, Download } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import toast from 'react-hot-toast'

export default function Passwords() {
  const [data, setData] = useState<PasswordAnalysis | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      // Let backend auto-detect the latest database
      const analysis = await apiService.getPasswordAnalysis()
      setData(analysis)
    } catch (error: any) {
      console.error('Error loading password analysis:', error)
      toast.error('Error loading password analysis')
    } finally {
      setLoading(false)
    }
  }

  const exportToCSV = () => {
    if (!data) return
    
    const headers = ['URL', 'Application', 'Username', 'Password', 'Category']
    const rows = data.vulnerable_credentials.map(c => [
      c.url,
      c.application,
      c.username,
      c.password,
      c.category
    ])
    
    const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `eyewitness-passwords-${new Date().toISOString()}.csv`
    a.click()
    toast.success('CSV exported successfully')
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400">No data available</p>
      </div>
    )
  }

  const chartData = data.application_statistics.map(app => ({
    name: app.application.length > 15 ? app.application.substring(0, 15) + '...' : app.application,
    successRate: app.success_rate,
    total: app.total_tested,
    successful: app.successful,
  }))

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">Análisis de Contraseñas</h1>
        <button
          onClick={exportToCSV}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors flex items-center space-x-2"
        >
          <Download className="h-4 w-4" />
          <span>Exportar CSV</span>
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm mb-1">Credenciales Vulnerables</p>
              <p className="text-3xl font-bold text-red-400">{data.total_vulnerable}</p>
            </div>
            <div className="bg-red-500/10 p-3 rounded-lg">
              <AlertTriangle className="h-6 w-6 text-red-400" />
            </div>
          </div>
        </div>
        <div className="glass rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm mb-1">Aplicaciones Analizadas</p>
              <p className="text-3xl font-bold text-white">{data.application_statistics.length}</p>
            </div>
            <div className="bg-primary-500/10 p-3 rounded-lg">
              <Shield className="h-6 w-6 text-primary-400" />
            </div>
          </div>
        </div>
        <div className="glass rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm mb-1">Tasa de Éxito Promedio</p>
              <p className="text-3xl font-bold text-yellow-400">
                {data.application_statistics.length > 0
                  ? Math.round(
                      data.application_statistics.reduce((acc, app) => acc + app.success_rate, 0) /
                        data.application_statistics.length
                    )
                  : 0}
                %
              </p>
            </div>
            <div className="bg-yellow-500/10 p-3 rounded-lg">
              <CheckCircle className="h-6 w-6 text-yellow-400" />
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="glass rounded-xl p-6">
        <h2 className="text-xl font-bold text-white mb-4">Tasa de Éxito por Aplicación</h2>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis 
              dataKey="name" 
              stroke="#94a3b8"
              angle={-45}
              textAnchor="end"
              height={100}
            />
            <YAxis stroke="#94a3b8" />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#1e293b', 
                border: '1px solid #334155',
                borderRadius: '8px'
              }}
              formatter={(value: number) => [`${value.toFixed(1)}%`, 'Tasa de Éxito']}
            />
            <Bar dataKey="successRate" fill="#ef4444" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recommendations */}
      {data.recommendations.length > 0 && (
        <div className="glass rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Recomendaciones de Seguridad</h2>
          <div className="space-y-3">
            {data.recommendations.map((rec, idx) => (
              <div key={idx} className="bg-slate-800/50 rounded-lg p-4 border-l-4 border-primary-500">
                <p className="text-slate-300">{rec}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Vulnerable Credentials Table */}
      <div className="glass rounded-xl overflow-hidden">
        <div className="p-6 border-b border-slate-700">
          <h2 className="text-xl font-bold text-white">Credenciales Vulnerables Encontradas</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-800">
              <tr>
                <th className="text-left py-3 px-4 text-slate-300">URL</th>
                <th className="text-left py-3 px-4 text-slate-300">Aplicación</th>
                <th className="text-left py-3 px-4 text-slate-300">Usuario</th>
                <th className="text-left py-3 px-4 text-slate-300">Contraseña</th>
                <th className="text-left py-3 px-4 text-slate-300">Categoría</th>
              </tr>
            </thead>
            <tbody>
              {data.vulnerable_credentials.map((cred, idx) => (
                <tr key={idx} className="border-b border-slate-800 hover:bg-slate-800/50">
                  <td className="py-3 px-4">
                    <a
                      href={cred.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary-400 hover:text-primary-300"
                    >
                      {cred.url}
                    </a>
                  </td>
                  <td className="py-3 px-4 text-white">{cred.application}</td>
                  <td className="py-3 px-4 text-red-400 font-mono">{cred.username}</td>
                  <td className="py-3 px-4 text-red-400 font-mono">{cred.password}</td>
                  <td className="py-3 px-4 text-slate-400">{cred.category}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Application Statistics */}
      <div className="glass rounded-xl overflow-hidden">
        <div className="p-6 border-b border-slate-700">
          <h2 className="text-xl font-bold text-white">Estadísticas por Aplicación</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-800">
              <tr>
                <th className="text-left py-3 px-4 text-slate-300">Aplicación</th>
                <th className="text-right py-3 px-4 text-slate-300">Total Probadas</th>
                <th className="text-right py-3 px-4 text-slate-300">Exitosas</th>
                <th className="text-right py-3 px-4 text-slate-300">Tasa de Éxito</th>
              </tr>
            </thead>
            <tbody>
              {data.application_statistics.map((stat, idx) => (
                <tr key={idx} className="border-b border-slate-800 hover:bg-slate-800/50">
                  <td className="py-3 px-4 text-white">{stat.application}</td>
                  <td className="py-3 px-4 text-right text-slate-300">{stat.total_tested}</td>
                  <td className="py-3 px-4 text-right text-red-400 font-semibold">
                    {stat.successful}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={`font-semibold ${
                      stat.success_rate > 50 
                        ? 'text-red-400'
                        : stat.success_rate > 25
                        ? 'text-yellow-400'
                        : 'text-green-400'
                    }`}>
                      {stat.success_rate.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

