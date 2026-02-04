import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { CheckSquare, Plus, X, RefreshCw } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

interface Task {
  id: string;
  title: string;
  description: string | null;
  status: string;
  priority: number;
  project: string | null;
  created_at: string;
}

export function TasksWidget() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTasks();
  }, []);

  async function fetchTasks() {
    setLoading(true);
    try {
      // Get pending and in_progress tasks
      const res = await fetch(`${API_BASE}/tasks/queue?limit=20`);
      if (!res.ok) throw new Error('Failed to fetch tasks');
      const data = await res.json();
      setTasks(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function createTask(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim()) return;

    setCreating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newTitle.trim(),
          description: newDescription.trim() || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create task');
      }
      const task = await res.json();
      setTasks([task, ...tasks]);
      setNewTitle('');
      setNewDescription('');
      setShowForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setCreating(false);
    }
  }

  function getStatusColor(status: string) {
    switch (status) {
      case 'completed':
        return 'bg-green-600';
      case 'in_progress':
        return 'bg-blue-600';
      case 'blocked':
        return 'bg-red-600';
      default:
        return 'bg-yellow-600';
    }
  }

  function getPriorityColor(priority: number) {
    if (priority >= 80) return 'text-red-400';
    if (priority >= 60) return 'text-orange-400';
    if (priority >= 40) return 'text-yellow-400';
    return 'text-gray-400';
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-200 flex items-center gap-2">
          <CheckSquare className="w-5 h-5 text-blue-400" />
          Tasks Queue
        </h3>
        <div className="flex items-center gap-1">
          <button
            onClick={fetchTasks}
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200"
          >
            {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-3 p-2 bg-red-900/30 border border-red-700 rounded text-red-300 text-sm">
          {error}
        </div>
      )}

      {showForm && (
        <form onSubmit={createTask} className="mb-4 p-3 bg-gray-900 rounded-lg">
          <input
            type="text"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="Task title"
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
                setNewTitle('');
                setNewDescription('');
              }}
              className="px-3 py-1.5 text-sm text-gray-400 hover:text-gray-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!newTitle.trim() || creating}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-sm text-white disabled:opacity-50"
            >
              {creating ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      )}

      {loading && tasks.length === 0 ? (
        <div className="text-center py-4 text-gray-500">Loading...</div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-6 text-gray-500">
          <p>No tasks in queue</p>
          <button
            onClick={() => setShowForm(true)}
            className="mt-2 text-blue-400 hover:text-blue-300 text-sm"
          >
            Create your first task
          </button>
        </div>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {tasks.map((task) => (
            <Link
              key={task.id}
              to={`/tasks/${task.id}`}
              className="block p-3 bg-gray-900 hover:bg-gray-700 rounded-lg transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${getStatusColor(task.status)}`}
                    />
                    <span className="text-sm text-gray-200 truncate">
                      {task.title}
                    </span>
                  </div>
                  {task.project && (
                    <span className="text-xs text-gray-500 ml-4">
                      {task.project}
                    </span>
                  )}
                </div>
                <div className="text-right flex-shrink-0">
                  <div className={`text-lg font-bold ${getPriorityColor(task.priority)}`}>
                    {task.priority}
                  </div>
                  <div className="text-xs text-gray-500">priority</div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
