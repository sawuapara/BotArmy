import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { API_BASE } from '../lib/config';

interface RequireAuthProps {
  children: React.ReactNode;
}

interface SessionStatus {
  is_unlocked: boolean;
  user_id: string | null;
}

export function RequireAuth({ children }: RequireAuthProps) {
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function checkSession() {
      try {
        const res = await fetch(`${API_BASE}/vault/session`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
        }
      } catch (e) {
        console.error('Failed to check session:', e);
      } finally {
        setLoading(false);
      }
    }
    checkSession();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-gray-400">Checking authentication...</div>
      </div>
    );
  }

  // Not authenticated - redirect to login
  if (!status?.is_unlocked || !status?.user_id) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
