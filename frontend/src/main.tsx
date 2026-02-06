import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App'
import { DatabaseViewer } from './components/DatabaseViewer'
import { ProjectView } from './components/ProjectView'
import { TaskView } from './components/TaskView'
import { VaultView } from './components/VaultView'
import { LoginPage } from './components/LoginPage'
import { RequireAuth } from './components/RequireAuth'
import { VaultProvider } from './context/VaultContext'
import { NamespaceProvider } from './context/NamespaceContext'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <NamespaceProvider>
      <VaultProvider>
        <BrowserRouter>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected routes */}
            <Route path="/" element={<RequireAuth><App /></RequireAuth>} />
            <Route path="/database" element={<RequireAuth><DatabaseViewer /></RequireAuth>} />
            <Route path="/projects/:projectId" element={<RequireAuth><ProjectView /></RequireAuth>} />
            <Route path="/tasks/:taskId" element={<RequireAuth><TaskView /></RequireAuth>} />
            <Route path="/vault" element={<RequireAuth><VaultView /></RequireAuth>} />
          </Routes>
        </BrowserRouter>
      </VaultProvider>
    </NamespaceProvider>
  </React.StrictMode>,
)
