import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App'
import { DatabaseViewer } from './components/DatabaseViewer'
import { ProjectView } from './components/ProjectView'
import { TaskView } from './components/TaskView'
import { VaultView } from './components/VaultView'
import { VaultProvider } from './context/VaultContext'
import { NamespaceProvider } from './context/NamespaceContext'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <NamespaceProvider>
      <VaultProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<App />} />
            <Route path="/database" element={<DatabaseViewer />} />
            <Route path="/projects/:projectId" element={<ProjectView />} />
            <Route path="/tasks/:taskId" element={<TaskView />} />
            <Route path="/vault" element={<VaultView />} />
          </Routes>
        </BrowserRouter>
      </VaultProvider>
    </NamespaceProvider>
  </React.StrictMode>,
)
