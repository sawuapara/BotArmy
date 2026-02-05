import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { API_BASE } from '../lib/config';

export interface Namespace {
  id: string;
  name: string;
  description: string | null;
  project_count?: number;
}

interface NamespaceContextType {
  namespaces: Namespace[];
  selectedNamespace: string; // 'All' or namespace id
  setSelectedNamespace: (id: string) => void;
  isLoading: boolean;
}

const NamespaceContext = createContext<NamespaceContextType | null>(null);

export function NamespaceProvider({ children }: { children: ReactNode }) {
  const [namespaces, setNamespaces] = useState<Namespace[]>([]);
  const [selectedNamespace, setSelectedNamespace] = useState<string>('All');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchNamespaces = async () => {
      try {
        const res = await fetch(`${API_BASE}/organization/namespaces`);
        if (!res.ok) throw new Error('Failed to fetch namespaces');
        const data = await res.json();
        setNamespaces(data);
      } catch (e) {
        console.error('Failed to fetch namespaces:', e);
      } finally {
        setIsLoading(false);
      }
    };

    fetchNamespaces();
  }, []);

  return (
    <NamespaceContext.Provider
      value={{
        namespaces,
        selectedNamespace,
        setSelectedNamespace,
        isLoading,
      }}
    >
      {children}
    </NamespaceContext.Provider>
  );
}

export function useNamespace() {
  const context = useContext(NamespaceContext);
  if (!context) {
    throw new Error('useNamespace must be used within a NamespaceProvider');
  }
  return context;
}
