import { ExternalLink, Clock, User, Tag } from 'lucide-react';
import type { TicketInfo, WorkerState } from '../types';

interface ActiveTicketProps {
  ticket: TicketInfo | null;
  workerState: WorkerState | null;
}

export function ActiveTicket({ ticket, workerState }: ActiveTicketProps) {
  if (!ticket) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="text-center text-gray-500">
          No active ticket. Start a session to begin.
        </div>
      </div>
    );
  }

  const jiraUrl = `https://mecanoconsulting.atlassian.net/browse/${ticket.key}`;

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-900/50 to-gray-800 px-6 py-4 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl font-bold text-green-400">{ticket.key}</span>
            <span className="px-2 py-1 text-xs rounded bg-gray-700 text-gray-300">
              {ticket.ticket_type}
            </span>
            <span className="px-2 py-1 text-xs rounded bg-blue-900 text-blue-300">
              {ticket.status}
            </span>
          </div>
          <a
            href={jiraUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-sm text-gray-400 hover:text-blue-400"
          >
            Open in JIRA
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
        <h2 className="text-lg text-gray-200 mt-2">{ticket.summary}</h2>
      </div>

      {/* Details */}
      <div className="p-6 grid grid-cols-2 gap-4">
        <div className="flex items-center gap-2 text-sm">
          <Tag className="w-4 h-4 text-gray-500" />
          <span className="text-gray-400">Project:</span>
          <span className="text-gray-200">{ticket.project}</span>
        </div>

        {ticket.assignee && (
          <div className="flex items-center gap-2 text-sm">
            <User className="w-4 h-4 text-gray-500" />
            <span className="text-gray-400">Assignee:</span>
            <span className="text-gray-200">{ticket.assignee}</span>
          </div>
        )}

        {ticket.estimated_hours && (
          <div className="flex items-center gap-2 text-sm">
            <Clock className="w-4 h-4 text-gray-500" />
            <span className="text-gray-400">Estimate:</span>
            <span className="text-gray-200">{ticket.estimated_hours}h</span>
          </div>
        )}

        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-400">Priority Score:</span>
          <span className="text-xl font-bold text-green-400">
            {ticket.priority_score.toFixed(0)}
          </span>
        </div>

        {ticket.labels.length > 0 && (
          <div className="col-span-2 flex items-center gap-2 text-sm flex-wrap">
            <span className="text-gray-400">Labels:</span>
            {ticket.labels.map((label) => (
              <span
                key={label}
                className="px-2 py-0.5 text-xs rounded bg-gray-700 text-gray-300"
              >
                {label}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Worker Status */}
      {workerState && (
        <div className="px-6 py-4 bg-gray-900 border-t border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm text-gray-400">Worker:</span>
              <span className="ml-2 text-gray-200">{workerState.status}</span>
            </div>
            <div>
              <span className="text-sm text-gray-400">Current Node:</span>
              <span className="ml-2 font-mono text-blue-400">
                {workerState.current_node}
              </span>
            </div>
          </div>
          {workerState.nodes_completed.length > 0 && (
            <div className="mt-2 text-xs text-gray-500">
              Completed: {workerState.nodes_completed.join(' → ')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
