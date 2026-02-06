import { useState, useEffect, useCallback } from 'react';
import { Cloud, Bot, RefreshCw, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { API_BASE } from '../lib/config';

interface ServiceStatus {
  name: string;
  status: 'connected' | 'disconnected' | 'error' | 'checking';
  latency?: number;
  error?: string;
}

interface StatusResponse {
  aws: { status: string; latency_ms?: number; error?: string };
  anthropic: { status: string; latency_ms?: number; error?: string };
  gemini: { status: string; latency_ms?: number; error?: string };
  openai: { status: string; latency_ms?: number; error?: string };
}

export function ConnectionStatusWidget() {
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: 'AWS', status: 'checking' },
    { name: 'Anthropic', status: 'checking' },
    { name: 'Gemini', status: 'checking' },
    { name: 'OpenAI', status: 'checking' },
  ]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const checkStatus = useCallback(async () => {
    setIsRefreshing(true);
    setServices((prev) =>
      prev.map((s) => ({ ...s, status: 'checking' as const }))
    );

    try {
      const res = await fetch(`${API_BASE}/status/connections`);
      if (!res.ok) throw new Error('Failed to fetch status');
      const data: StatusResponse = await res.json();

      setServices([
        {
          name: 'AWS',
          status: data.aws.status as ServiceStatus['status'],
          latency: data.aws.latency_ms,
          error: data.aws.error,
        },
        {
          name: 'Anthropic',
          status: data.anthropic.status as ServiceStatus['status'],
          latency: data.anthropic.latency_ms,
          error: data.anthropic.error,
        },
        {
          name: 'Gemini',
          status: data.gemini.status as ServiceStatus['status'],
          latency: data.gemini.latency_ms,
          error: data.gemini.error,
        },
        {
          name: 'OpenAI',
          status: data.openai.status as ServiceStatus['status'],
          latency: data.openai.latency_ms,
          error: data.openai.error,
        },
      ]);
      setLastChecked(new Date());
    } catch (e) {
      // If endpoint doesn't exist yet, show as disconnected
      setServices([
        { name: 'AWS', status: 'disconnected' },
        { name: 'Anthropic', status: 'disconnected' },
        { name: 'Gemini', status: 'disconnected' },
        { name: 'OpenAI', status: 'disconnected' },
      ]);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    checkStatus();
    // Check every 60 seconds
    const interval = setInterval(checkStatus, 60000);
    return () => clearInterval(interval);
  }, [checkStatus]);

  const getStatusIcon = (status: ServiceStatus['status']) => {
    switch (status) {
      case 'connected':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'disconnected':
        return <XCircle className="w-4 h-4 text-gray-500" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      case 'checking':
        return <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />;
    }
  };

  const getStatusColor = (status: ServiceStatus['status']) => {
    switch (status) {
      case 'connected':
        return 'text-green-400';
      case 'disconnected':
        return 'text-gray-500';
      case 'error':
        return 'text-red-400';
      case 'checking':
        return 'text-blue-400';
    }
  };

  const getServiceIcon = (name: string) => {
    if (name === 'AWS') {
      return <Cloud className="w-4 h-4" />;
    }
    return <Bot className="w-4 h-4" />;
  };

  const connectedCount = services.filter((s) => s.status === 'connected').length;

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700">
      <div className="p-3 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cloud className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-gray-200">Connections</span>
          <span className="text-xs text-gray-500">
            ({connectedCount}/{services.length})
          </span>
        </div>
        <button
          onClick={checkStatus}
          disabled={isRefreshing}
          className="p-1 hover:bg-gray-700 rounded"
          title="Refresh status"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 text-gray-400 ${isRefreshing ? 'animate-spin' : ''}`}
          />
        </button>
      </div>

      <div className="p-2 space-y-1">
        {services.map((service) => (
          <div
            key={service.name}
            className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-gray-700/50"
            title={service.error || undefined}
          >
            <div className="flex items-center gap-2">
              <span className="text-gray-400">{getServiceIcon(service.name)}</span>
              <span className="text-sm text-gray-300">{service.name}</span>
            </div>
            <div className="flex items-center gap-2">
              {service.latency && service.status === 'connected' && (
                <span className="text-xs text-gray-500">{service.latency}ms</span>
              )}
              {getStatusIcon(service.status)}
            </div>
          </div>
        ))}
      </div>

      {lastChecked && (
        <div className="px-3 py-1.5 border-t border-gray-700 text-xs text-gray-500">
          Last checked: {lastChecked.toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}
