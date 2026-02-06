import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { FolderOpen, Plus, GripVertical } from 'lucide-react';
import { useNamespace } from '../context/NamespaceContext';
import { API_BASE } from '../lib/config';
import { NewProjectModal } from './NewProjectModal';

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
  sort_order: number;
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
  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dropTargetIndex, setDropTargetIndex] = useState<number | null>(null); // Where the line indicator shows

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

  // Get default namespace for new projects
  function getDefaultNamespaceId() {
    if (selectedNamespace && selectedNamespace !== 'All') {
      return selectedNamespace;
    }
    return namespaces.length > 0 ? namespaces[0].id : '';
  }

  function handleProjectCreated() {
    // Refresh projects list
    fetchProjects();
    setShowModal(false);
  }

  // Drag and drop handlers
  function handleDragStart(e: React.DragEvent, index: number) {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    // Add some delay to allow the drag image to be created
    requestAnimationFrame(() => {
      const target = e.target as HTMLDivElement;
      target.style.opacity = '0.4';
    });
  }

  function handleDragEnd(e: React.DragEvent) {
    const target = e.target as HTMLDivElement;
    target.style.opacity = '1';
    setDraggedIndex(null);
    setDropTargetIndex(null);
  }

  function handleDragOver(e: React.DragEvent, index: number) {
    e.preventDefault();
    if (draggedIndex === null) return;

    // Calculate if we're in the top or bottom half of the element
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const midpoint = rect.top + rect.height / 2;
    const insertIndex = e.clientY < midpoint ? index : index + 1;

    // Don't show indicator if dropping in same position
    if (insertIndex === draggedIndex || insertIndex === draggedIndex + 1) {
      setDropTargetIndex(null);
    } else {
      setDropTargetIndex(insertIndex);
    }
  }

  function handleDragLeave(e: React.DragEvent) {
    // Only clear if we're leaving the container entirely
    const relatedTarget = e.relatedTarget as HTMLElement;
    if (!relatedTarget || !e.currentTarget.contains(relatedTarget)) {
      setDropTargetIndex(null);
    }
  }

  async function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    if (draggedIndex === null || dropTargetIndex === null) {
      setDropTargetIndex(null);
      return;
    }

    // Calculate the actual insert position
    let insertAt = dropTargetIndex;
    if (dropTargetIndex > draggedIndex) {
      insertAt = dropTargetIndex - 1;
    }

    if (insertAt === draggedIndex) {
      setDropTargetIndex(null);
      return;
    }

    // Reorder the projects array
    const newProjects = [...projects];
    const [draggedProject] = newProjects.splice(draggedIndex, 1);
    newProjects.splice(insertAt, 0, draggedProject);

    // Update local state immediately for responsive UI
    setProjects(newProjects);
    setDropTargetIndex(null);

    // Update sort_order for all affected projects
    try {
      const updates = newProjects.map((project, idx) => ({
        id: project.id,
        sort_order: idx,
      }));

      // Update each project's sort_order
      await Promise.all(
        updates.map((update) =>
          fetch(`${API_BASE}/projects/${update.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sort_order: update.sort_order }),
          })
        )
      );
    } catch (err) {
      // Revert on error
      setError('Failed to save order');
      fetchProjects();
    }
  }

  return (
    <>
    {showModal && (
      <NewProjectModal
        onClose={() => setShowModal(false)}
        onProjectCreated={handleProjectCreated}
        defaultNamespaceId={getDefaultNamespaceId()}
      />
    )}
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-200 flex items-center gap-2">
          <FolderOpen className="w-5 h-5 text-yellow-500" />
          Projects
        </h3>
        <button
          onClick={() => setShowModal(true)}
          className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {error && (
        <div className="mb-3 p-2 bg-red-900/30 border border-red-700 rounded text-red-300 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-4 text-gray-500">Loading...</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-6 text-gray-500">
          <p>No projects yet</p>
          <button
            onClick={() => setShowModal(true)}
            className="mt-2 text-blue-400 hover:text-blue-300 text-sm"
          >
            Create your first project
          </button>
        </div>
      ) : (
        <div
          className="space-y-1"
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
        >
          {projects.map((project, index) => (
            <div key={project.id} className="relative">
              {/* Drop indicator line - shows ABOVE this item */}
              {dropTargetIndex === index && (
                <div className="absolute -top-1 left-0 right-0 h-0.5 bg-blue-500 rounded-full z-10">
                  <div className="absolute -left-1 -top-1 w-2 h-2 bg-blue-500 rounded-full" />
                  <div className="absolute -right-1 -top-1 w-2 h-2 bg-blue-500 rounded-full" />
                </div>
              )}

              <div
                draggable
                onDragStart={(e) => handleDragStart(e, index)}
                onDragEnd={handleDragEnd}
                onDragOver={(e) => handleDragOver(e, index)}
                onDragLeave={handleDragLeave}
                className={`flex items-stretch bg-gray-900 rounded-lg transition-opacity ${
                  draggedIndex === index ? 'opacity-40' : 'opacity-100'
                }`}
              >
                {/* Drag Handle */}
                <div
                  className="flex items-center px-2 cursor-grab active:cursor-grabbing text-gray-500 hover:text-gray-300 hover:bg-gray-700 rounded-l-lg"
                  title="Drag to reorder"
                >
                  <GripVertical className="w-4 h-4" />
                </div>

                {/* Project Content */}
                <Link
                  to={`/projects/${project.id}`}
                  className="flex-1 p-3 hover:bg-gray-700 rounded-r-lg transition-colors"
                  onClick={(e) => {
                    // Prevent navigation when dragging
                    if (draggedIndex !== null) {
                      e.preventDefault();
                    }
                  }}
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
              </div>

              {/* Drop indicator line - shows BELOW the last item */}
              {index === projects.length - 1 && dropTargetIndex === projects.length && (
                <div className="absolute -bottom-1 left-0 right-0 h-0.5 bg-blue-500 rounded-full z-10">
                  <div className="absolute -left-1 -top-1 w-2 h-2 bg-blue-500 rounded-full" />
                  <div className="absolute -right-1 -top-1 w-2 h-2 bg-blue-500 rounded-full" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
    </>
  );
}
