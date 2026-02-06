import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { API_BASE } from '../lib/config';

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // Load remembered username from backend on mount
  useEffect(() => {
    async function loadLastUsername() {
      try {
        const res = await fetch(`${API_BASE}/vault/last-username`);
        if (res.ok) {
          const data = await res.json();
          if (data.username) {
            setUsername(data.username);
            setRememberMe(true);
          }
        }
      } catch (e) {
        console.error('Failed to load last username:', e);
      }
    }
    loadLastUsername();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !password) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/vault/unlock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          password,
          remember_username: rememberMe,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Invalid credentials');
      }

      // Successfully authenticated - redirect to dashboard
      navigate('/', { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-blue-600 rounded-full mb-3">
              <Lock className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-xl font-semibold text-gray-200">Jarvis</h1>
            <p className="text-sm text-gray-400 mt-1">Enter your master password</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-gray-200 focus:outline-none focus:border-blue-500"
                placeholder="Username or email"
                autoFocus={!username}
                autoComplete="username"
              />
            </div>

            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 pr-10 bg-gray-900 border border-gray-600 rounded text-gray-200 focus:outline-none focus:border-blue-500"
                placeholder="Master password"
                autoFocus={!!username}
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-200"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="rememberMe"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="w-4 h-4 bg-gray-900 border-gray-600 rounded text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-800"
              />
              <label htmlFor="rememberMe" className="ml-2 text-sm text-gray-400">
                Remember username
              </label>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-2 bg-red-900/30 border border-red-700 rounded text-red-300 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full py-2 bg-blue-600 hover:bg-blue-500 rounded text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
