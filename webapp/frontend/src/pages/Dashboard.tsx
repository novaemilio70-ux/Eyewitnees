import { useEffect, useState } from 'react'
import { apiService, DashboardStats } from '../services/api'
import { 
  Shield, 
  AlertTriangle, 
  Database,
  Zap,
  Key
} from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import toast from 'react-hot-toast'

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadDashboard()
  }, [])

  const loadDashboard = async () => {
    try {
      setLoading(true)
      // Let backend auto-detect the latest database
      const data = await apiService.getDashboardStats()
      setStats(data)
    } catch (error: any) {
      console.error('Error loading dashboard:', error)
      toast.error('Error loading dashboard. Make sure the database path is correct.')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400">No data available. Please load a database.</p>
      </div>
    )
  }

  const statCards = [
    {
      title: 'Total Escaneos',
      value: stats.stats.total_scans,
      icon: Database,
      color: 'text-blue-400',
      bgColor: 'bg-blue-500/10',
    },
    {
      title: 'Apps con Default Creds',
      value: stats.stats.critical_vulnerabilities,
      icon: AlertTriangle,
      color: 'text-red-400',
      bgColor: 'bg-red-500/10',
    },
    {
      title: 'Aplicaciones Detectadas',
      value: stats.stats.applications_detected,
      icon: Shield,
      color: 'text-green-400',
      bgColor: 'bg-green-500/10',
    },
    {
      title: 'Aplicaciones Probadas',
      value: stats.stats.credentials_found,
      icon: Key,
      color: 'text-yellow-400',
      bgColor: 'bg-yellow-500/10',
    },
  ]

  const topAppsData = stats.top_vulnerable_apps.map(app => ({
    name: app.name,
    vulnerabilities: app.vulnerabilities,
  }))

  // Datos para Tecnologías Más Usadas (ordenado por total descendente)
  const techUsageData = Object.entries(stats.tech_risk_map || {})
    .map(([tech, data]) => ({
      name: tech,
      total: data.total,
      vulnerable: data.vulnerable,
      riskRate: data.total > 0 ? (data.vulnerable / data.total) * 100 : 0,
    }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 10)

  // Datos para Distribución por Categorías (ordenado por total descendente)
  const categoryDistributionData = Object.entries(stats.category_risk_map || {})
    .map(([category, data]) => ({
      name: category,
      total: data.total,
      vulnerable: data.vulnerable,
      riskRate: data.total > 0 ? (data.vulnerable / data.total) * 100 : 0,
    }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 10)

  // Datos para Riesgo por Categoría (ordenado por riesgo descendente)
  const categoryRiskData = Object.entries(stats.category_risk_map || {})
    .map(([category, data]) => ({
      name: category,
      total: data.total,
      vulnerable: data.vulnerable,
      riskRate: data.total > 0 ? (data.vulnerable / data.total) * 100 : 0,
    }))
    .sort((a, b) => b.riskRate - a.riskRate)
    .slice(0, 10)

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">Dashboard de Seguridad</h1>
        <button
          onClick={loadDashboard}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors flex items-center space-x-2"
        >
          <Zap className="h-4 w-4" />
          <span>Actualizar</span>
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((card) => {
          const Icon = card.icon
          return (
            <div
              key={card.title}
              className="glass rounded-xl p-6 hover:scale-105 transition-transform"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-slate-400 text-sm mb-1">{card.title}</p>
                  <p className="text-3xl font-bold text-white">{card.value}</p>
                </div>
                <div className={`${card.bgColor} p-3 rounded-lg`}>
                  <Icon className={`h-6 w-6 ${card.color}`} />
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Vulnerable Apps */}
        <div className="glass rounded-xl p-6">
          <h2 
            className="text-xl font-bold text-white mb-4 cursor-help" 
            title="Muestra las 10 aplicaciones con más equipos que tienen credenciales por defecto exitosas (PWNED). Ordenado por cantidad de vulnerabilidades."
          >
            Top 10 Aplicaciones Más Vulnerables
          </h2>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={topAppsData} margin={{ bottom: 120, right: 20, top: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis 
                dataKey="name" 
                stroke="#94a3b8"
                angle={-45}
                textAnchor="end"
                height={150}
                interval={0}
              />
              <YAxis stroke="#94a3b8" />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1e293b', 
                  border: '1px solid #334155',
                  borderRadius: '8px'
                }}
              />
              <Bar dataKey="vulnerabilities" fill="#ef4444" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Technology Usage Map */}
        <div className="glass rounded-xl p-6">
          <h2 
            className="text-xl font-bold text-white mb-4 cursor-help" 
            title="Muestra las 10 cabeceras de servidor más detectadas en los escaneos. Ordenado por frecuencia (cantidad de veces que aparece)."
          >
            Cabeceras más Vistas
          </h2>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={techUsageData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" stroke="#94a3b8" />
              <YAxis dataKey="name" type="category" stroke="#94a3b8" width={180} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1e293b', 
                  border: '1px solid #334155',
                  borderRadius: '8px'
                }}
                formatter={(value: number, name: string) => {
                  if (name === 'total') return [value, 'Total de Usos']
                  if (name === 'vulnerable') return [value, 'Vulnerables']
                  return [value, name]
                }}
              />
              <Bar dataKey="total" fill="#22c55e" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Categories Chart Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Distribution */}
        <div className="glass rounded-xl p-6">
          <h2 
            className="text-xl font-bold text-white mb-4 cursor-help" 
            title="Muestra las 10 categorías con más equipos detectados. Ordenado por cantidad total de equipos en cada categoría."
          >
            Distribución por Categorías
          </h2>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={categoryDistributionData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" stroke="#94a3b8" />
              <YAxis dataKey="name" type="category" stroke="#94a3b8" width={180} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1e293b', 
                  border: '1px solid #334155',
                  borderRadius: '8px'
                }}
                formatter={(value: number, name: string) => {
                  if (name === 'total') return [value, 'Total']
                  if (name === 'vulnerable') return [value, 'Vulnerables']
                  return [value, name]
                }}
              />
              <Bar dataKey="total" fill="#0ea5e9" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Category Risk Map */}
        <div className="glass rounded-xl p-6">
          <h2 
            className="text-xl font-bold text-white mb-4 cursor-help" 
            title="Muestra el porcentaje de equipos comprometidos por categoría. Calculado como: (Vulnerables / Total) × 100%. Ordenado por mayor riesgo."
          >
            Riesgo por Categoría
          </h2>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={categoryRiskData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" stroke="#94a3b8" />
              <YAxis dataKey="name" type="category" stroke="#94a3b8" width={180} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1e293b', 
                  border: '1px solid #334155',
                  borderRadius: '8px'
                }}
                formatter={(value: number) => [`${value.toFixed(1)}%`, 'Tasa de Riesgo']}
              />
              <Bar dataKey="riskRate" fill="#8b5cf6" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top Vulnerable Apps Table */}
      <div className="glass rounded-xl p-6">
        <h2 
          className="text-xl font-bold text-white mb-4 cursor-help" 
          title="Tabla que muestra las aplicaciones con más equipos que tienen credenciales por defecto configuradas. Incluye el nivel de riesgo basado en la cantidad de equipos vulnerables."
        >
          Aplicaciones con Mas Credenciales por Defecto
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-3 px-4 text-slate-300">Aplicación</th>
                <th className="text-right py-3 px-4 text-slate-300">Cantidad de Equipos</th>
                <th className="text-right py-3 px-4 text-slate-300">Nivel de Riesgo</th>
              </tr>
            </thead>
            <tbody>
              {stats.top_vulnerable_apps.map((app, index) => (
                <tr key={index} className="border-b border-slate-800 hover:bg-slate-800/50">
                  <td className="py-3 px-4 text-white">{app.name}</td>
                  <td className="py-3 px-4 text-right text-red-400 font-semibold">
                    {app.vulnerabilities}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      app.vulnerabilities > 5 
                        ? 'bg-red-500/20 text-red-400'
                        : app.vulnerabilities > 2
                        ? 'bg-yellow-500/20 text-yellow-400'
                        : 'bg-green-500/20 text-green-400'
                    }`}>
                      {app.vulnerabilities > 5 ? 'Crítico' : app.vulnerabilities > 2 ? 'Alto' : 'Medio'}
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

