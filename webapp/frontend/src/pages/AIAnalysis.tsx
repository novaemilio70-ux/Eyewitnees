import { useEffect, useState } from 'react'
import { apiService, type AIAnalysis as AIAnalysisType } from '../services/api'
import { Brain, AlertCircle, CheckCircle2 } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'

const COLORS = ['#22c55e', '#f59e0b', '#ef4444']

function AIAnalysisPage() {
  const [data, setData] = useState<AIAnalysisType | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      // Let backend auto-detect the latest database
      const analysis = await apiService.getAIAnalysis()
      setData(analysis)
    } catch (error: any) {
      console.error('Error loading AI analysis:', error)
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

  if (!data) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400">No data available</p>
      </div>
    )
  }

  const confidenceData = [
    { name: 'Alta', value: data.confidence_metrics.high, color: COLORS[0] },
    { name: 'Media', value: data.confidence_metrics.medium, color: COLORS[1] },
    { name: 'Baja', value: data.confidence_metrics.low, color: COLORS[2] },
  ]

  const techCount = data.technology_timeline.reduce((acc, item) => {
    acc[item.technology] = (acc[item.technology] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  const topTechs = Object.entries(techCount)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">Análisis de Detección IA</h1>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="glass rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm mb-1">Total Detecciones</p>
              <p className="text-3xl font-bold text-white">{data.total_detections}</p>
            </div>
            <div className="bg-primary-500/10 p-3 rounded-lg">
              <Brain className="h-6 w-6 text-primary-400" />
            </div>
          </div>
        </div>
        <div className="glass rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm mb-1">Alta Confianza</p>
              <p className="text-3xl font-bold text-green-400">{data.confidence_metrics.high}</p>
            </div>
            <div className="bg-green-500/10 p-3 rounded-lg">
              <CheckCircle2 className="h-6 w-6 text-green-400" />
            </div>
          </div>
        </div>
        <div className="glass rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm mb-1">Media Confianza</p>
              <p className="text-3xl font-bold text-yellow-400">{data.confidence_metrics.medium}</p>
            </div>
            <div className="bg-yellow-500/10 p-3 rounded-lg">
              <AlertCircle className="h-6 w-6 text-yellow-400" />
            </div>
          </div>
        </div>
        <div className="glass rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm mb-1">Baja Confianza</p>
              <p className="text-3xl font-bold text-red-400">{data.confidence_metrics.low}</p>
            </div>
            <div className="bg-red-500/10 p-3 rounded-lg">
              <AlertCircle className="h-6 w-6 text-red-400" />
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Confidence Distribution */}
        <div className="glass rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Distribución de Confianza</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={confidenceData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {confidenceData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Top Technologies */}
        <div className="glass rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Top 10 Tecnologías Detectadas</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={topTechs}>
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
              />
              <Bar dataKey="count" fill="#0ea5e9" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Detected Applications Gallery */}
      <div className="glass rounded-xl p-6">
        <h2 className="text-xl font-bold text-white mb-4">Aplicaciones Detectadas</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.detected_applications.map((app, idx) => (
            <div
              key={idx}
              className="bg-slate-800/50 rounded-lg p-4 border border-slate-700 hover:border-primary-500 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold text-white">{app.name}</h3>
                {app.vulnerable && (
                  <span className="px-2 py-1 rounded text-xs font-semibold bg-red-500/20 text-red-400 border border-red-500/50">
                    Vulnerable
                  </span>
                )}
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Detecciones:</span>
                  <span className="text-white font-semibold">{app.count}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Confianza:</span>
                  <span className={`font-semibold ${
                    app.confidence === 'high' 
                      ? 'text-green-400'
                      : app.confidence === 'medium'
                      ? 'text-yellow-400'
                      : 'text-red-400'
                  }`}>
                    {app.confidence.toUpperCase()}
                  </span>
                </div>
                {app.technologies.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs text-slate-400 mb-1">Tecnologías:</p>
                    <div className="flex flex-wrap gap-1">
                      {app.technologies.slice(0, 3).map((tech, techIdx) => (
                        <span
                          key={techIdx}
                          className="px-2 py-1 rounded text-xs bg-slate-700 text-slate-300"
                        >
                          {tech}
                        </span>
                      ))}
                      {app.technologies.length > 3 && (
                        <span className="px-2 py-1 rounded text-xs bg-slate-700 text-slate-300">
                          +{app.technologies.length - 3}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default AIAnalysisPage

