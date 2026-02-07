import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Reports from './pages/Reports'
import Passwords from './pages/Passwords'
import AIAnalysis from './pages/AIAnalysis'
import Gallery from './pages/Gallery'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/report" element={<Reports />} />
          <Route path="/passwords" element={<Passwords />} />
          <Route path="/ai-analysis" element={<AIAnalysis />} />
          <Route path="/gallery" element={<Gallery />} />
        </Routes>
      </Layout>
      <Toaster position="top-right" />
    </Router>
  )
}

export default App

