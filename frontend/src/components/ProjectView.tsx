import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Save, Trash2, FolderOpen, CheckSquare, LayoutDashboard, Database, Tag, X, Plus, ChevronDown } from 'lucide-react';
import { API_BASE } from '../lib/config';

interface Namespace {
  id: string;
  name: string;
  description: string | null;
}

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
  tags: string[];
  labels: LabelInfo[];
  repository_url: string | null;
  jira_project_key: string | null;
  salesforce_account_id: string | null;
  task_count: number;
  created_at: string;
  updated_at: string;
}

interface Task {
  id: string;
  title: string;
  status: string;
  priority: number;
  created_at: string;
}

export function ProjectView() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [namespaces, setNamespaces] = useState<Namespace[]>([]);
  const [availableLabels, setAvailableLabels] = useState<LabelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Editable fields
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [namespaceId, setNamespaceId] = useState('');
  const [hasChanges, setHasChanges] = useState(false);

  // Label management
  const [showLabelDropdown, setShowLabelDropdown] = useState(false);

  useEffect(() => {
    fetchNamespaces();
  }, []);

  useEffect(() => {
    if (projectId) {
      fetchProject();
      fetchProjectTasks();
    }
  }, [projectId]);

  useEffect(() => {
    if (namespaceId) {
      fetchLabelsForNamespace(namespaceId);
    }
  }, [namespaceId]);

  useEffect(() => {
    if (project) {
      setHasChanges(
        name !== project.name ||
        description !== (project.description || '') ||
        namespaceId !== project.namespace_id
      );
    }
  }, [name, description, namespaceId, project]);

  async function fetchNamespaces() {
    try {
      const res = await fetch(`${API_BASE}/organization/namespaces`);
      if (res.ok) {
        const data = await res.json();
        setNamespaces(data);
      }
    } catch (e) {
      console.error('Failed to fetch namespaces:', e);
    }
  }

  async function fetchLabelsForNamespace(nsId: string) {
    try {
      const res = await fetch(`${API_BASE}/organization/namespaces/${nsId}/labels`);
      if (res.ok) {
        const data = await res.json();
        setAvailableLabels(data);
      }
    } catch (e) {
      console.error('Failed to fetch labels:', e);
    }
  }

  async function fetchProject() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}`);
      if (!res.ok) throw new Error('Project not found');
      const data = await res.json();
      setProject(data);
      setName(data.name);
      setDescription(data.description || '');
      setNamespaceId(data.namespace_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function fetchProjectTasks() {
    try {
      const res = await fetch(`${API_BASE}/tasks?project=${projectId}&limit=50`);
      if (res.ok) {
        const data = await res.json();
        setTasks(data);
      }
    } catch (e) {
      console.error('Failed to fetch tasks:', e);
    }
  }

  async function saveProject() {
    if (!project || !hasChanges) return;

    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          namespace_id: namespaceId,
          description: description.trim() || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to save');
      }
      const updated = await res.json();
      setProject(updated);
      setHasChanges(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  }

  async function deleteProject() {
    if (!confirm('Are you sure you want to delete this project?')) return;

    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Failed to delete');
      navigate('/');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    }
  }

  async function addLabel(labelId: string) {
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/labels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label_id: labelId }),
      });
      if (res.ok) {
        const labels = await res.json();
        setProject({ ...project!, labels });
      }
    } catch (e) {
      console.error('Failed to add label:', e);
    }
    setShowLabelDropdown(false);
  }

  async function removeLabel(labelId: string) {
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/labels/${labelId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setProject({
          ...project!,
          labels: project!.labels.filter((l) => l.id !== labelId),
        });
      }
    } catch (e) {
      console.error('Failed to remove label:', e);
    }
  }

  function getStatusColor(status: string) {
    switch (status) {
      case 'completed':
        return 'text-green-400';
      case 'in_progress':
        return 'text-blue-400';
      case 'blocked':
        return 'text-red-400';
      default:
        return 'text-gray-400';
    }
  }

  // Get labels that aren't already on the project
  const unusedLabels = availableLabels.filter(
    (label) => !project?.labels.some((l) => l.id === label.id)
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error || 'Project not found'}</p>
          <Link to="/" className="text-blue-400 hover:text-blue-300">
            Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 hover:bg-gray-700 rounded"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <FolderOpen className="w-6 h-6 text-yellow-500" />
              <div>
                <h1 className="text-xl font-semibold">Project</h1>
                <p className="text-sm text-gray-400">
                  Created {new Date(project.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          </div>
          <nav className="flex items-center gap-2">
            <Link
              to="/"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-gray-700 hover:bg-gray-600 text-gray-300"
            >
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </Link>
            <Link
              to="/database"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-gray-700 hover:bg-gray-600 text-gray-300"
            >
              <Database className="w-4 h-4" />
              Database
            </Link>
          </nav>
        </div>
      </header>

      <main className="p-6 max-w-4xl mx-auto">
        {error && (
          <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded text-red-300">
            {error}
          </div>
        )}

        {/* Project Details */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 mb-6">
          <div className="space-y-4">
            {/* Namespace Selector */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Namespace</label>
              <div className="relative">
                <select
                  value={namespaceId}
                  onChange={(e) => setNamespaceId(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-900 border border-gray-600 rounded text-gray-200 appearance-none focus:outline-none focus:border-blue-500"
                >
                  {namespaces.map((ns) => (
                    <option key={ns.id} value={ns.id}>
                      {ns.name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
              </div>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-2 bg-gray-900 border border-gray-600 rounded text-gray-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                className="w-full px-4 py-2 bg-gray-900 border border-gray-600 rounded text-gray-200 focus:outline-none focus:border-blue-500 resize-none"
                placeholder="Add a description..."
              />
            </div>

            {/* Labels */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Labels</label>
              <div className="flex flex-wrap gap-2 items-center">
                {project.labels.map((label) => (
                  <span
                    key={label.id}
                    className="inline-flex items-center gap-1 text-sm px-2 py-1 rounded"
                    style={{
                      backgroundColor: label.color ? `${label.color}20` : '#374151',
                      color: label.color || '#9CA3AF',
                      border: `1px solid ${label.color || '#4B5563'}`,
                    }}
                  >
                    <Tag className="w-3 h-3" />
                    {label.name}
                    <button
                      onClick={() => removeLabel(label.id)}
                      className="ml-1 hover:opacity-70"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}

                {/* Add Label Button */}
                <div className="relative">
                  <button
                    onClick={() => setShowLabelDropdown(!showLabelDropdown)}
                    className="inline-flex items-center gap-1 text-sm px-2 py-1 rounded border border-dashed border-gray-600 text-gray-400 hover:text-gray-200 hover:border-gray-500"
                  >
                    <Plus className="w-3 h-3" />
                    Add Label
                  </button>

                  {showLabelDropdown && unusedLabels.length > 0 && (
                    <div className="absolute top-full left-0 mt-1 w-48 bg-gray-800 border border-gray-600 rounded shadow-lg z-10">
                      {unusedLabels.map((label) => (
                        <button
                          key={label.id}
                          onClick={() => addLabel(label.id)}
                          className="w-full px-3 py-2 text-left text-sm text-gray-200 hover:bg-gray-700 flex items-center gap-2"
                        >
                          {label.color && (
                            <span
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: label.color }}
                            />
                          )}
                          {label.name}
                        </button>
                      ))}
                    </div>
                  )}

                  {showLabelDropdown && unusedLabels.length === 0 && (
                    <div className="absolute top-full left-0 mt-1 w-48 bg-gray-800 border border-gray-600 rounded shadow-lg z-10 p-3 text-sm text-gray-400">
                      No more labels available in this namespace
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-gray-700">
              <button
                onClick={deleteProject}
                className="flex items-center gap-2 px-4 py-2 text-red-400 hover:text-red-300 hover:bg-red-900/20 rounded"
              >
                <Trash2 className="w-4 h-4" />
                Delete Project
              </button>

              <button
                onClick={saveProject}
                disabled={!hasChanges || saving}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Save className="w-4 h-4" />
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>

        {/* Project Tasks */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h2 className="font-semibold text-gray-200 flex items-center gap-2 mb-4">
            <CheckSquare className="w-5 h-5 text-blue-400" />
            Tasks ({tasks.length})
          </h2>

          {tasks.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No tasks in this project yet
            </div>
          ) : (
            <div className="space-y-2">
              {tasks.map((task) => (
                <Link
                  key={task.id}
                  to={`/tasks/${task.id}`}
                  className="block p-3 bg-gray-900 hover:bg-gray-700 rounded-lg transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-gray-200">{task.title}</span>
                    <div className="flex items-center gap-3">
                      <span className={`text-sm ${getStatusColor(task.status)}`}>
                        {task.status}
                      </span>
                      <span className="text-sm text-gray-500">
                        P{task.priority}
                      </span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
