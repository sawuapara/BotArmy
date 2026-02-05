import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FolderOpen, Plus, X, ChevronDown } from 'lucide-react';
import { useNamespace } from '../context/NamespaceContext';
import { API_BASE } from '../lib/config';

interface LabelInfo {
  id: string;
  name: string;
  color: string | null;
}

interface NamespaceInfo {
  id: string;
  name: string;
}

interface Project {
  id: string;
  name: string;
  namespace_id: string;
  namespace: NamespaceInfo | null;
  description: string | null;
  status: string;
  labels: LabelInfo[];
  task_count: number;
  created_at: string;
  updated_at: string;
}

interface ProjectsWidgetProps {
  selectedNamespace: string; // 'All' or namespace id
}

export function ProjectsWidget({ selectedNamespace }: ProjectsWidgetProps) {
  const { namespaces } = useNamespace();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newNamespaceId, setNewNamespaceId] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Set default namespace for new projects when namespaces load
  useEffect(() => {
    if (namespaces.length > 0 && !newNamespaceId) {
      setNewNamespaceId(namespaces[0].id);
    }
  }, [namespaces, newNamespaceId]);

  useEffect(() => {
    fetchProjects();
  }, [selectedNamespace]);

  async function fetchProjects() {
    try {
      setLoading(true);
      let url = `${API_BASE}/projects?status=active`;
      if (selectedNamespace && selectedNamespace !== 'All') {
        url += `&namespace_id=${selectedNamespace}`;
      }
      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to fetch projects');
      const data = await res.json();
      setProjects(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function createProject(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim() || !newNamespaceId) return;

    setCreating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName.trim(),
          namespace_id: newNamespaceId,
          description: newDescription.trim() || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create project');
      }
      const project = await res.json();
      setProjects([project, ...projects]);
      setNewName('');
      setNewDescription('');
      setShowForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-200 flex items-center gap-2">
          <FolderOpen className="w-5 h-5 text-yellow-500" />
          Projects
        </h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200"
        >
          {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
        </button>
      </div>

      {error && (
        <div className="mb-3 p-2 bg-red-900/30 border border-red-700 rounded text-red-300 text-sm">
          {error}
        </div>
      )}

      {showForm && (
        <form onSubmit={createProject} className="mb-4 p-3 bg-gray-900 rounded-lg">
          <div className="relative mb-2">
            <select
              value={newNamespaceId}
              onChange={(e) => setNewNamespaceId(e.target.value)}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-gray-200 text-sm appearance-none focus:outline-none focus:border-blue-500"
              required
            >
              {namespaces.map((ns) => (
                <option key={ns.id} value={ns.id}>
                  {ns.name}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Project name"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded text-gray-200 placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500"
            autoFocus
          />
          <textarea
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            placeholder="Description (optional)"
            rows={2}
            className="w-full mt-2 px-3 py-2 bg-gray-800 border border-gray-600 rounded text-gray-200 placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500 resize-none"
          />
          <div className="flex justify-end gap-2 mt-2">
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setNewName('');
                setNewDescription('');
              }}
              className="px-3 py-1.5 text-sm text-gray-400 hover:text-gray-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!newName.trim() || !newNamespaceId || creating}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-sm text-white disabled:opacity-50"
            >
              {creating ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="text-center py-4 text-gray-500">Loading...</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-6 text-gray-500">
          <p>No projects yet</p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-2 text-blue-400 hover:text-blue-300 text-sm"
          >
            Create your first project
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {projects.map((project) => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className="block p-3 bg-gray-900 hover:bg-gray-700 rounded-lg transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-200">{project.name}</span>
                  {project.namespace && (
                    <span className="text-xs px-1.5 py-0.5 bg-gray-700 rounded text-gray-400">
                      {project.namespace.name}
                    </span>
                  )}
                </div>
                <span className="text-xs px-2 py-0.5 bg-gray-700 rounded text-gray-400">
                  {project.task_count} tasks
                </span>
              </div>
              {project.labels.length > 0 && (
                <div className="flex gap-1 mt-1.5">
                  {project.labels.slice(0, 3).map((label) => (
                    <span
                      key={label.id}
                      className="text-xs px-1.5 py-0.5 rounded"
                      style={{
                        backgroundColor: label.color ? `${label.color}20` : '#374151',
                        color: label.color || '#9CA3AF',
                        border: `1px solid ${label.color || '#4B5563'}`,
                      }}
                    >
                      {label.name}
                    </span>
                  ))}
                  {project.labels.length > 3 && (
                    <span className="text-xs text-gray-500">
                      +{project.labels.length - 3}
                    </span>
                  )}
                </div>
              )}
              {project.description && (
                <p className="text-sm text-gray-400 mt-1 truncate">
                  {project.description}
                </p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
