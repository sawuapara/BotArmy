import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { CheckSquare, Plus, RefreshCw } from 'lucide-react';
import { API_BASE } from '../lib/config';
import { NewTaskModal } from './NewTaskModal';

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
  const [showModal, setShowModal] = useState(false);
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
    <>
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
              onClick={() => setShowModal(true)}
              className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200"
              title="New Task"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-3 p-2 bg-red-900/30 border border-red-700 rounded text-red-300 text-sm">
            {error}
          </div>
        )}

        {loading && tasks.length === 0 ? (
          <div className="text-center py-4 text-gray-500">Loading...</div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-6 text-gray-500">
            <p>No tasks in queue</p>
            <button
              onClick={() => setShowModal(true)}
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

      {showModal && <NewTaskModal onClose={() => setShowModal(false)} />}
    </>
  );
}
