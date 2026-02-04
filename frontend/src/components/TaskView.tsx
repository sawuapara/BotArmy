import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Save, Trash2, CheckSquare, LayoutDashboard, Database } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

interface Task {
  id: string;
  title: string;
  description: string | null;
  status: string;
  priority: number;
  source: string;
  source_id: string | null;
  source_url: string | null;
  assigned_to: string | null;
  tags: string[];
  project: string | null;
  estimated_hours: number | null;
  actual_hours: number | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  due_date: string | null;
}

const STATUS_OPTIONS = ['pending', 'in_progress', 'blocked', 'completed', 'cancelled'];

export function TaskView() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();

  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Editable fields
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState('pending');
  const [priority, setPriority] = useState(50);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (taskId) {
      fetchTask();
    }
  }, [taskId]);

  useEffect(() => {
    if (task) {
      setHasChanges(
        title !== task.title ||
        description !== (task.description || '') ||
        status !== task.status ||
        priority !== task.priority
      );
    }
  }, [title, description, status, priority, task]);

  async function fetchTask() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`);
      if (!res.ok) throw new Error('Task not found');
      const data = await res.json();
      setTask(data);
      setTitle(data.title);
      setDescription(data.description || '');
      setStatus(data.status);
      setPriority(data.priority);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function saveTask() {
    if (!task || !hasChanges) return;

    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim() || null,
          status,
          priority,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to save');
      }
      const updated = await res.json();
      setTask(updated);
      setHasChanges(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  }

  async function deleteTask() {
    if (!confirm('Are you sure you want to delete this task?')) return;

    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Failed to delete');
      navigate('/');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    }
  }

  function getStatusColor(s: string) {
    switch (s) {
      case 'completed':
        return 'bg-green-600';
      case 'in_progress':
        return 'bg-blue-600';
      case 'blocked':
        return 'bg-red-600';
      case 'cancelled':
        return 'bg-gray-600';
      default:
        return 'bg-yellow-600';
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error || 'Task not found'}</p>
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
              onClick={() => navigate(-1)}
              className="p-2 hover:bg-gray-700 rounded"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <CheckSquare className="w-6 h-6 text-blue-400" />
              <div>
                <h1 className="text-xl font-semibold">Task</h1>
                <p className="text-sm text-gray-400">
                  Created {new Date(task.created_at).toLocaleDateString()}
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

        {/* Task Details */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
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

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Status</label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-900 border border-gray-600 rounded text-gray-200 focus:outline-none focus:border-blue-500"
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {s.replace('_', ' ')}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">
                  Priority ({priority})
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={priority}
                  onChange={(e) => setPriority(parseInt(e.target.value))}
                  className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
                />
              </div>
            </div>

            {/* Read-only info */}
            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-700">
              <div>
                <span className="text-sm text-gray-400">Source:</span>
                <span className="ml-2 text-gray-200">{task.source}</span>
              </div>
              {task.source_id && (
                <div>
                  <span className="text-sm text-gray-400">Source ID:</span>
                  <span className="ml-2 text-gray-200">{task.source_id}</span>
                </div>
              )}
              {task.assigned_to && (
                <div>
                  <span className="text-sm text-gray-400">Assigned to:</span>
                  <span className="ml-2 text-gray-200">{task.assigned_to}</span>
                </div>
              )}
              {task.project && (
                <div>
                  <span className="text-sm text-gray-400">Project:</span>
                  <span className="ml-2 text-gray-200">{task.project}</span>
                </div>
              )}
            </div>

            {/* Timestamps */}
            <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-700 text-sm">
              <div>
                <span className="text-gray-400">Updated:</span>
                <span className="ml-2 text-gray-300">
                  {new Date(task.updated_at).toLocaleString()}
                </span>
              </div>
              {task.started_at && (
                <div>
                  <span className="text-gray-400">Started:</span>
                  <span className="ml-2 text-gray-300">
                    {new Date(task.started_at).toLocaleString()}
                  </span>
                </div>
              )}
              {task.completed_at && (
                <div>
                  <span className="text-gray-400">Completed:</span>
                  <span className="ml-2 text-gray-300">
                    {new Date(task.completed_at).toLocaleString()}
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-gray-700">
              <button
                onClick={deleteTask}
                className="flex items-center gap-2 px-4 py-2 text-red-400 hover:text-red-300 hover:bg-red-900/20 rounded"
              >
                <Trash2 className="w-4 h-4" />
                Delete Task
              </button>

              <button
                onClick={saveTask}
                disabled={!hasChanges || saving}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Save className="w-4 h-4" />
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
