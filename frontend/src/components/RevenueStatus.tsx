import { DollarSign, TrendingUp, TrendingDown } from 'lucide-react';
import type { RevenueStatus as RevenueStatusType } from '../types';

interface RevenueStatusProps {
  status: RevenueStatusType | null;
  workType: 'consulting' | 'product' | null;
}

export function RevenueStatus({ status, workType }: RevenueStatusProps) {
  if (!status) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="text-gray-500 text-sm">Loading revenue status...</div>
      </div>
    );
  }

  const percentage = (status.billed_hours / status.target_hours) * 100;
  const isOnTrack = percentage >= 100;

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-green-400" />
          <span className="font-semibold text-gray-200">Monthly Revenue</span>
        </div>
        <span className="text-sm text-gray-400">{status.month}</span>
      </div>

      {/* Progress bar */}
      <div className="h-3 bg-gray-700 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full transition-all duration-500 ${
            isOnTrack ? 'bg-green-500' : 'bg-yellow-500'
          }`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-1">
          {isOnTrack ? (
            <TrendingUp className="w-4 h-4 text-green-400" />
          ) : (
            <TrendingDown className="w-4 h-4 text-yellow-400" />
          )}
          <span className="text-gray-300">
            {status.billed_hours.toFixed(1)} / {status.target_hours} hours
          </span>
        </div>
        <span className={isOnTrack ? 'text-green-400' : 'text-yellow-400'}>
          {percentage.toFixed(0)}%
        </span>
      </div>

      {/* Work type indicator */}
      <div className="mt-3 pt-3 border-t border-gray-700 flex items-center justify-between">
        <span className="text-sm text-gray-400">Current Focus:</span>
        <span
          className={`px-3 py-1 rounded text-sm font-medium ${
            workType === 'consulting'
              ? 'bg-blue-900 text-blue-300'
              : 'bg-purple-900 text-purple-300'
          }`}
        >
          {workType === 'consulting' ? 'Consulting (Billable)' : 'Product Work'}
        </span>
      </div>

      {!isOnTrack && (
        <div className="mt-2 text-xs text-yellow-400">
          Need {status.remaining_hours.toFixed(1)} more hours to hit target
        </div>
      )}
    </div>
  );
}
