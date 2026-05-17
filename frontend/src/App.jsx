import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { FileText, LayoutTemplate, GitBranch, Sparkles, UploadCloud } from 'lucide-react'
import UploadPage from './pages/UploadPage'
import TemplatesPage from './pages/TemplatesPage'
import TemplatePage from './pages/TemplatePage'
import MappingPage from './pages/MappingPage'
import GeneratePage from './pages/GeneratePage'

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>DocTemplAI</h1>
        <p>AI Template Engine</p>
      </div>
      <nav className="sidebar-nav">
        <div className="nav-section-label">Workflow</div>
        <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <UploadCloud size={15} /> Upload Document
        </NavLink>
        <NavLink to="/templates" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <LayoutTemplate size={15} /> Templates
        </NavLink>
      </nav>
    </aside>
  )
}

export default function App() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/templates/:id" element={<TemplatePage />} />
          <Route path="/templates/:id/map" element={<MappingPage />} />
          <Route path="/templates/:id/generate" element={<GeneratePage />} />
        </Routes>
      </main>
    </div>
  )
}