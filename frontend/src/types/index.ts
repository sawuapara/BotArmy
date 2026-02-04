// State types matching backend

export interface TicketInfo {
  key: string;
  source: 'jira' | 'salesforce';
  project: string;
  summary: string;
  status: string;
  ticket_type: 'bug' | 'feature' | 'question' | 'task';
  priority_score: number;
  created_date: string;
  updated_date: string;
  labels: string[];
  assignee: string | null;
  estimated_hours: number | null;
  completion_pct: number | null;
}

export interface RevenueStatus {
  target_hours: number;
  billed_hours: number;
  remaining_hours: number;
  is_below_target: boolean;
  month: string;
}

export interface ClientRevenue {
  client_name: string;
  hours: number;
  rate: number;
  revenue: number;
}

export interface RevenueMetrics {
  // MTD (Month to Date) metrics
  mtd_hours: number;
  mtd_revenue: number;
  mtd_goal_hours: number;
  mtd_goal_revenue: number;
  mtd_gap_hours: number;
  mtd_gap_revenue: number;

  // Progress
  hours_progress_pct: number;
  revenue_progress_pct: number;

  // Forecast
  month_forecast_hours: number;
  month_forecast_gross: number;
  month_forecast_net: number;
  month_forecast_annualized_gross: number;
  month_forecast_annualized_net: number;

  // Breakdown by client
  by_client: ClientRevenue[];

  // Meta
  month: string;
  days_elapsed: number;
  days_in_month: number;
  days_remaining: number;
  last_updated: string;
}

export interface WorkerState {
  status: 'running' | 'complete' | 'blocked' | 'error';
  ticket_key: string;
  ticket_type: string;
  current_node: string;
  started_at: string | null;
  nodes_completed: string[];
  chain_of_thought: string[];
}

export interface OrchestratorState {
  session_id: string;
  started_at: string;
  revenue_status: RevenueStatus | null;
  work_type: 'consulting' | 'product' | null;
  ticket_queue: TicketInfo[];
  current_ticket: TicketInfo | null;
  current_node: string;
  thought_log: string[];
  active_worker: string | null;
  worker_state: WorkerState | null;
  is_paused: boolean;
  paused_tickets: Record<string, unknown>[];
  error: string | null;
}

export interface Session {
  session_id: string;
  status: 'created' | 'running' | 'paused' | 'completed' | 'error';
  current_node: string | null;
  current_ticket: TicketInfo | null;
  thought_log: string[];
}

// WebSocket message types
export type WSMessage =
  | { type: 'initial_state'; state: OrchestratorState }
  | { type: 'state_update'; node: string; thought_log: string[]; current_ticket: TicketInfo | null }
  | { type: 'queue_updated'; queue: TicketInfo[] }
  | { type: 'session_paused'; session_id: string }
  | { type: 'interrupted'; reason: string }
  | { type: 'completed'; state: OrchestratorState }
  | { type: 'error'; error: string };
