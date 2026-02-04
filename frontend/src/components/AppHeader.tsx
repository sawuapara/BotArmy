import { Link, useLocation } from 'react-router-dom';
import { Database, Lock, Wifi, WifiOff, Play, Pause, RefreshCw } from 'lucide-react';
import { useNamespace } from '../context/NamespaceContext';

interface AppHeaderProps {
  // Session-related props (only for dashboard)
  session?: { session_id: string; status: string } | null;
  isConnected?: boolean;
  isLoading?: boolean;
  onCreateSession?: () => void;
  onStartSession?: () => void;
  onPauseSession?: () => void;
  // Vault-related props
  isVault?: boolean;
  onLockVault?: () => void;
  currentUser?: { first_name: string; last_name: string } | null;
}

export function AppHeader({
  session,
  isConnected,
  isLoading,
  onCreateSession,
  onStartSession,
  onPauseSession,
  isVault,
  onLockVault,
  currentUser,
}: AppHeaderProps) {
  const location = useLocation();
  const { namespaces, selectedNamespace, setSelectedNamespace } = useNamespace();

  const isActive = (path: string) => location.pathname === path;

  return (
    <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-100">
              Jarvis Dashboard
            </h1>
            <p className="text-sm text-gray-400">
              MecanoLabs / MecanoConsulting Work Prioritization
            </p>
          </div>
          <nav className="flex items-center gap-2 ml-8">
            <Link
              to="/"
              className={`px-3 py-1.5 rounded text-sm ${
                isActive('/')
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
              }`}
            >
              Dashboard
            </Link>
            <Link
              to="/database"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm ${
                isActive('/database')
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
              }`}
            >
              <Database className="w-4 h-4" />
              Database
            </Link>
            <Link
              to="/vault"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm ${
                isActive('/vault')
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
              }`}
            >
              <Lock className="w-4 h-4" />
              Vault
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-4">
          {/* Current user (if available) */}
          {currentUser && (
            <div className="text-sm text-gray-400">
              <span className="text-gray-200 font-medium">
                {currentUser.first_name} {currentUser.last_name}
              </span>
            </div>
          )}

          {/* Namespace selector */}
          <select
            value={selectedNamespace}
            onChange={(e) => setSelectedNamespace(e.target.value)}
            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-gray-200"
          >
            <option value="All">All Namespaces</option>
            {namespaces.map((ns) => (
              <option key={ns.id} value={ns.id}>
                {ns.name}
              </option>
            ))}
          </select>

          {/* Connection status (dashboard only) */}
          {!isVault && (
            <div className="flex items-center gap-2 text-sm">
              {isConnected ? (
                <>
                  <Wifi className="w-4 h-4 text-green-400" />
                  <span className="text-green-400">Connected</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4 text-gray-500" />
                  <span className="text-gray-500">Disconnected</span>
                </>
              )}
            </div>
          )}

          {/* Vault lock button */}
          {isVault && onLockVault && (
            <button
              onClick={onLockVault}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg text-white"
            >
              <Lock className="w-4 h-4" />
              Lock Vault
            </button>
          )}

          {/* Session controls (dashboard only) */}
          {!isVault && (
            <>
              {!session ? (
                <button
                  onClick={onCreateSession}
                  disabled={isLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium disabled:opacity-50"
                >
                  <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                  New Session
                </button>
              ) : session.status === 'running' ? (
                <button
                  onClick={onPauseSession}
                  className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-500 rounded-lg text-white font-medium"
                >
                  <Pause className="w-4 h-4" />
                  Pause
                </button>
              ) : (
                <button
                  onClick={onStartSession}
                  disabled={isLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-white font-medium disabled:opacity-50"
                >
                  <Play className="w-4 h-4" />
                  {session.status === 'created' ? 'Start' : 'Resume'}
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </header>
  );
}
