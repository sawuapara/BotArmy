import { useState, useEffect, useCallback } from 'react';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Target,
  Calendar,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import type { RevenueMetrics, ClientRevenue } from '../types';
import { API_BASE } from '../lib/config';

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value: number, decimals = 1): string {
  return value.toFixed(decimals);
}

interface MetricCardProps {
  label: string;
  value: string;
  subValue?: string;
  trend?: 'up' | 'down' | 'neutral';
  highlight?: 'green' | 'yellow' | 'red' | 'blue' | 'purple';
}

function MetricCard({ label, value, subValue, trend, highlight = 'blue' }: MetricCardProps) {
  const highlightColors = {
    green: 'text-green-400',
    yellow: 'text-yellow-400',
    red: 'text-red-400',
    blue: 'text-blue-400',
    purple: 'text-purple-400',
  };

  return (
    <div className="bg-gray-750 rounded-lg p-3">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlightColors[highlight]}`}>
        {value}
        {trend === 'up' && <TrendingUp className="inline w-4 h-4 ml-1" />}
        {trend === 'down' && <TrendingDown className="inline w-4 h-4 ml-1" />}
      </div>
      {subValue && <div className="text-xs text-gray-500">{subValue}</div>}
    </div>
  );
}

interface ClientBreakdownProps {
  clients: ClientRevenue[];
}

function ClientBreakdown({ clients }: ClientBreakdownProps) {
  if (clients.length === 0) return null;

  const totalRevenue = clients.reduce((sum, c) => sum + c.revenue, 0);

  return (
    <div className="mt-4 space-y-2">
      <div className="text-xs text-gray-400 uppercase tracking-wide">By Client</div>
      {clients.map((client) => {
        const pct = totalRevenue > 0 ? (client.revenue / totalRevenue) * 100 : 0;
        return (
          <div key={client.client_name} className="flex items-center gap-3">
            <div className="flex-1">
              <div className="flex justify-between text-sm">
                <span className="text-gray-300">{client.client_name}</span>
                <span className="text-gray-400">
                  {formatNumber(client.hours)}h @ ${client.rate}/hr
                </span>
              </div>
              <div className="h-1.5 bg-gray-700 rounded-full mt-1 overflow-hidden">
                <div
                  className="h-full bg-blue-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
            <div className="text-sm font-medium text-green-400 w-20 text-right">
              {formatCurrency(client.revenue)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function RevenueWidget() {
  const [metrics, setMetrics] = useState<RevenueMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showBreakdown, setShowBreakdown] = useState(false);

  const fetchMetrics = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/revenue/metrics`);
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to fetch revenue data');
      }
      const data = await res.json();
      setMetrics(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    // Refresh every 5 minutes
    const interval = setInterval(fetchMetrics, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchMetrics]);

  if (isLoading && !metrics) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="flex items-center gap-2 text-gray-400">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span>Loading revenue data...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="text-red-400 mb-3">Error: {error}</div>
        <button
          onClick={fetchMetrics}
          className="flex items-center gap-2 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  if (!metrics) return null;

  const isOnTrack = metrics.revenue_progress_pct >= 100;
  const isPaceGood = metrics.month_forecast_gross >= metrics.mtd_goal_revenue;

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-green-400" />
            <span className="font-semibold text-gray-200">MecanoConsulting Revenue</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-400">
              <Calendar className="w-4 h-4 inline mr-1" />
              {metrics.month} (Day {metrics.days_elapsed}/{metrics.days_in_month})
            </span>
            <button
              onClick={fetchMetrics}
              disabled={isLoading}
              className="p-1.5 hover:bg-gray-700 rounded"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 text-gray-400 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Progress */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-300">MTD Progress</span>
          </div>
          <span className={`text-sm font-medium ${isOnTrack ? 'text-green-400' : 'text-yellow-400'}`}>
            {metrics.revenue_progress_pct}%
          </span>
        </div>
        <div className="h-4 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-500 ${
              isOnTrack ? 'bg-green-500' : 'bg-yellow-500'
            }`}
            style={{ width: `${Math.min(metrics.revenue_progress_pct, 100)}%` }}
          />
        </div>
        <div className="flex justify-between mt-2 text-sm">
          <span className="text-gray-400">
            {formatCurrency(metrics.mtd_revenue)} / {formatCurrency(metrics.mtd_goal_revenue)}
          </span>
          {!isOnTrack && (
            <span className="text-yellow-400">
              Gap: {formatCurrency(metrics.mtd_gap_revenue)}
            </span>
          )}
        </div>
      </div>

      {/* MTD Metrics Grid */}
      <div className="p-4 grid grid-cols-3 gap-3 border-b border-gray-700">
        <MetricCard
          label="MTD Revenue"
          value={formatCurrency(metrics.mtd_revenue)}
          subValue={`${formatNumber(metrics.mtd_hours)}h billed`}
          highlight={isOnTrack ? 'green' : 'yellow'}
        />
        <MetricCard
          label="MTD Goal"
          value={formatCurrency(metrics.mtd_goal_revenue)}
          subValue={`${metrics.mtd_goal_hours}h target`}
          highlight="blue"
        />
        <MetricCard
          label="MTD Gap"
          value={metrics.mtd_gap_revenue > 0 ? formatCurrency(metrics.mtd_gap_revenue) : '$0'}
          subValue={metrics.mtd_gap_hours > 0 ? `${formatNumber(metrics.mtd_gap_hours)}h remaining` : 'Target met!'}
          highlight={metrics.mtd_gap_revenue > 0 ? 'red' : 'green'}
        />
      </div>

      {/* Forecast Section */}
      <div className="p-4 border-b border-gray-700">
        <div className="text-xs text-gray-400 uppercase tracking-wide mb-3">
          Month Forecast (at current pace)
        </div>
        <div className="grid grid-cols-2 gap-3">
          <MetricCard
            label="Forecast Gross"
            value={formatCurrency(metrics.month_forecast_gross)}
            subValue={`${formatNumber(metrics.month_forecast_hours)}h projected`}
            trend={isPaceGood ? 'up' : 'down'}
            highlight={isPaceGood ? 'green' : 'yellow'}
          />
          <MetricCard
            label="Forecast Net"
            value={formatCurrency(metrics.month_forecast_net)}
            subValue="After overhead & taxes"
            highlight="purple"
          />
        </div>
      </div>

      {/* Annualized Section */}
      <div className="p-4 border-b border-gray-700">
        <div className="text-xs text-gray-400 uppercase tracking-wide mb-3">
          Annualized (based on current month)
        </div>
        <div className="grid grid-cols-2 gap-3">
          <MetricCard
            label="Annual Gross"
            value={formatCurrency(metrics.month_forecast_annualized_gross)}
            highlight="blue"
          />
          <MetricCard
            label="Annual Net"
            value={formatCurrency(metrics.month_forecast_annualized_net)}
            highlight="purple"
          />
        </div>
      </div>

      {/* Client Breakdown Toggle */}
      <button
        onClick={() => setShowBreakdown(!showBreakdown)}
        className="w-full p-3 flex items-center justify-between text-sm text-gray-400 hover:bg-gray-750 transition-colors"
      >
        <span>Client Breakdown ({metrics.by_client.length} clients)</span>
        {showBreakdown ? (
          <ChevronUp className="w-4 h-4" />
        ) : (
          <ChevronDown className="w-4 h-4" />
        )}
      </button>

      {showBreakdown && (
        <div className="p-4 pt-0">
          <ClientBreakdown clients={metrics.by_client} />
        </div>
      )}

      {/* Last Updated */}
      <div className="px-4 py-2 text-xs text-gray-500 text-right border-t border-gray-700">
        Last updated: {new Date(metrics.last_updated).toLocaleTimeString()}
      </div>
    </div>
  );
}
