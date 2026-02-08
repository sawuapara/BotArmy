import { useState, useEffect, useRef, useMemo } from 'react';
import { X, Send, ChevronDown, Code, ChevronRight, Loader2, Server } from 'lucide-react';
import { API_BASE } from '../lib/config';
import { useAgentStream, type AgentInfo } from '../hooks/useAgentStream';
import type { UniverseEvent, LLMCallDetail } from '../types';
import { WorkerDetailModal, type Worker } from './WorkerDetailModal';

interface Namespace {
  id: string;
  name: string;
}

interface Project {
  id: string;
  name: string;
  namespace_id?: string | null;
  namespace?: { name: string } | null;
}

interface ApiDebugInfo {
  endpoint: string;
  model: string;
  system: string;
  messages: Array<{ role: string; content: unknown }>;
  tools: unknown[] | null;
  thinking: unknown | null;
  max_tokens: number;
  iterations?: number;
  worker_id?: string;
  worker_name?: string;
}

interface UsageInfo {
  input_tokens: number;
  output_tokens: number;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  turn?: number;
  usage?: UsageInfo;
  request_debug?: ApiDebugInfo;
  response_raw?: unknown;
  llmCalls?: LLMCallDetail[];
}

interface NewTaskModalProps {
  onClose: () => void;
}

// Collapsible section component
function DebugSection({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-gray-700 rounded">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800"
      >
        <ChevronRight
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-90' : ''}`}
        />
        {title}
      </button>
      {isOpen && (
        <div className="px-3 py-2 border-t border-gray-700 bg-gray-800/50">
          {children}
        </div>
      )}
    </div>
  );
}

// Debug Panel — two-column layout: left = LLM call list, right = inspector
function DebugPanel({
  messages,
  onClose,
  initialTurn,
  onOpenWorker,
  liveEvents,
  isStreaming,
  streamingAgentInfo,
  liveLlmCalls,
}: {
  messages: Message[];
  onClose: () => void;
  initialTurn?: number | null;
  onOpenWorker?: (workerId: string) => void;
  liveEvents?: UniverseEvent[];
  isStreaming?: boolean;
  streamingAgentInfo?: AgentInfo;
  liveLlmCalls?: LLMCallDetail[];
}) {
  const turnsEndRef = useRef<HTMLDivElement>(null);
  const [selectedCallIdx, setSelectedCallIdx] = useState<number | null>(null);
  const [selectedTurn, setSelectedTurn] = useState<number | null>(initialTurn ?? null);

  // Collect all LLM calls: from completed messages + live streaming
  const allLlmCalls = useMemo(() => {
    const calls: LLMCallDetail[] = [];
    for (const m of messages) {
      if (m.llmCalls) calls.push(...m.llmCalls);
    }
    if (isStreaming && liveLlmCalls) {
      calls.push(...liveLlmCalls);
    }
    return calls;
  }, [messages, isStreaming, liveLlmCalls]);

  const hasLlmCalls = allLlmCalls.length > 0 || isStreaming;

  const assistantMessages = useMemo(
    () => messages.filter((m) => m.role === 'assistant' && m.request_debug),
    [messages]
  );

  // Auto-scroll to bottom of call list
  useEffect(() => {
    turnsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [allLlmCalls.length, assistantMessages.length]);

  // Auto-select matching call when initialTurn changes
  useEffect(() => {
    if (initialTurn !== null && initialTurn !== undefined) {
      if (allLlmCalls.length > 0) {
        const idx = allLlmCalls.findIndex((c) => c.turnNumber === initialTurn && c.iterationNumber === 0);
        if (idx !== -1) setSelectedCallIdx(idx);
      } else {
        setSelectedTurn(initialTurn);
      }
    }
  }, [initialTurn, allLlmCalls]);

  // Selected call detail (new mode)
  const selectedCall = selectedCallIdx !== null ? allLlmCalls[selectedCallIdx] : null;

  // Selected message detail (legacy mode)
  const detailMessage = useMemo(() => {
    if (selectedCall) return null;
    if (selectedTurn !== null) {
      return assistantMessages.find((m) => m.turn === selectedTurn) || null;
    }
    return null;
  }, [selectedCall, selectedTurn, assistantMessages]);

  const totalTokens = messages.reduce(
    (acc, m) => ({
      input: acc.input + (m.usage?.input_tokens || 0),
      output: acc.output + (m.usage?.output_tokens || 0),
    }),
    { input: 0, output: 0 }
  );

  // Add live streaming tokens to totals
  const displayTokens = {
    input: totalTokens.input + (isStreaming && streamingAgentInfo ? streamingAgentInfo.totalInputTokens : 0),
    output: totalTokens.output + (isStreaming && streamingAgentInfo ? streamingAgentInfo.totalOutputTokens : 0),
  };

  // Group calls by turn number for display
  const groupedCalls = useMemo(() => {
    const groups: Map<number, LLMCallDetail[]> = new Map();
    for (const call of allLlmCalls) {
      const existing = groups.get(call.turnNumber) || [];
      existing.push(call);
      groups.set(call.turnNumber, existing);
    }
    return groups;
  }, [allLlmCalls]);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative bg-gray-900 rounded-lg border border-gray-600 w-[80vw] h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-gray-700">
          <div className="flex items-center gap-4">
            <h3 className="text-sm font-medium text-gray-200">API Debug</h3>
            <div className="flex items-center gap-3 text-xs">
              <span className="text-orange-400">
                {hasLlmCalls
                  ? `Calls: ${allLlmCalls.length}${isStreaming ? '+' : ''}`
                  : `Turns: ${assistantMessages.length}`}
              </span>
              <span className="text-green-400">
                In: {displayTokens.input.toLocaleString()}
              </span>
              <span className="text-blue-400">
                Out: {displayTokens.output.toLocaleString()}
              </span>
              {isStreaming && (
                <span className="text-blue-400 animate-pulse">● live</span>
              )}
            </div>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-gray-700 rounded">
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        {/* Two-column body */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left: LLM call list grouped by turn, or conversation fallback */}
          <div className="flex-1 flex flex-col border-r border-gray-700">
            <div className="px-4 py-2 border-b border-gray-700 text-xs text-gray-500">
              {hasLlmCalls ? 'LLM API Calls' : 'Conversation Turns'}
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {/* LLM call list when calls are available */}
              {allLlmCalls.length > 0 && Array.from(groupedCalls.entries()).map(([turnNum, calls]) => (
                <div key={turnNum}>
                  <div className="text-xs text-gray-500 font-medium mb-1 px-1">
                    Turn {turnNum}
                  </div>
                  {calls.map((call) => {
                    const globalIdx = allLlmCalls.indexOf(call);
                    const isSelected = selectedCallIdx === globalIdx;
                    return (
                      <button
                        key={call.id}
                        onClick={() => setSelectedCallIdx(isSelected ? null : globalIdx)}
                        className={`w-full text-left px-3 py-2 rounded text-xs mb-1 transition-colors ${
                          isSelected
                            ? 'bg-blue-900/40 border border-blue-700 text-blue-200'
                            : 'hover:bg-gray-800 text-gray-300 border border-transparent'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono">
                            {call.turnNumber}.{call.iterationNumber}
                          </span>
                          <span className="text-gray-500">
                            {call.stopReason === 'tool_use' ? '🔧' : '✓'}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-0.5 text-gray-500">
                          <span>{call.model || '?'}</span>
                          <span>·</span>
                          <span className="text-green-500">{call.inputTokens}</span>
                          <span>+</span>
                          <span className="text-blue-500">{call.outputTokens}</span>
                          <span>tok</span>
                          {call.durationMs > 0 && (
                            <>
                              <span>·</span>
                              <span>{(call.durationMs / 1000).toFixed(1)}s</span>
                            </>
                          )}
                        </div>
                        {call.toolCalls.length > 0 && (
                          <div className="mt-0.5 text-yellow-500 truncate">
                            {call.toolCalls.map((t) => t.name).join(', ')}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              ))}
              {/* Fallback: conversation turn list when no LLM calls */}
              {!hasLlmCalls && messages.map((message) => (
                <div key={message.id}>
                  {message.role === 'user' && (
                    <div className="flex justify-end mb-2">
                      <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-blue-600/80 text-white">
                        <pre className="whitespace-pre-wrap font-sans text-xs">
                          {message.content}
                        </pre>
                      </div>
                    </div>
                  )}
                  {message.role === 'assistant' && (
                    <div
                      onClick={() => {
                        setSelectedCallIdx(null);
                        setSelectedTurn(selectedTurn === message.turn ? null : (message.turn ?? null));
                      }}
                      className={`mb-2 rounded-lg px-3 py-2 cursor-pointer transition-colors border-2 ${
                        selectedTurn === message.turn
                          ? 'border-cyan-500 bg-gray-800'
                          : 'border-transparent bg-gray-800 hover:border-gray-600'
                      }`}
                    >
                      {message.turn && (
                        <div className="flex items-center gap-2 text-xs mb-1">
                          <span className="font-mono text-gray-400">Turn {message.turn}</span>
                          {message.usage && (
                            <span className="text-gray-600">
                              {message.usage.input_tokens}+{message.usage.output_tokens} tok
                            </span>
                          )}
                          {message.request_debug?.iterations !== undefined && (
                            <span className="text-purple-500">
                              {message.request_debug.iterations} iter
                            </span>
                          )}
                        </div>
                      )}
                      <pre className="whitespace-pre-wrap font-sans text-xs text-gray-200">
                        {message.content}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
              {/* Live event stream when streaming but no calls yet */}
              {isStreaming && allLlmCalls.length === 0 && (
                <div className="border border-blue-800/50 rounded-lg p-3 bg-blue-950/20">
                  <div className="flex items-center gap-2 mb-2 text-xs text-blue-300">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span className="font-medium">Waiting for first call...</span>
                  </div>
                </div>
              )}
              {/* Live event log */}
              {isStreaming && liveEvents && liveEvents.length > 0 && (
                <div className="border border-blue-800/50 rounded-lg p-3 bg-blue-950/20 mt-2">
                  <div className="flex items-center gap-2 mb-2 text-xs text-blue-300">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span className="font-medium">Live Stream</span>
                    {streamingAgentInfo?.name && (
                      <span className="text-gray-400">· {streamingAgentInfo.name}</span>
                    )}
                  </div>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {liveEvents.slice(-30).map((evt, i) => {
                      const colorMap: Record<string, string> = {
                        llm_response: 'text-green-400',
                        tool_call: 'text-yellow-400',
                        tool_result: 'text-purple-400',
                        turn_start: 'text-blue-400',
                        iteration_detail: 'text-cyan-400',
                      };
                      const color = colorMap[evt.type] || 'text-gray-500';
                      let preview = '';
                      if (evt.type === 'llm_response') {
                        preview = ((evt.data.text as string) || '').slice(0, 80);
                      } else if (evt.type === 'tool_call') {
                        preview = (evt.data.tool as string) || '';
                      } else if (evt.type === 'turn_start') {
                        preview = `Turn ${evt.data.turn || '?'}`;
                      }
                      return (
                        <div key={i} className={`text-xs font-mono ${color} truncate`}>
                          <span className="opacity-60">{evt.type}</span>{' '}
                          {preview && <span className="opacity-80">{preview}</span>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              <div ref={turnsEndRef} />
            </div>
          </div>

          {/* Right: inspector panel */}
          <div className="flex-1 flex flex-col overflow-y-auto p-4 space-y-3">
            {selectedCall ? (
              <>
                <div className="text-xs text-gray-500 mb-1">
                  Call {selectedCall.turnNumber}.{selectedCall.iterationNumber}
                </div>

                {/* Summary row */}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  <div>
                    <span className="text-xs text-gray-500">Model </span>
                    <code className="text-yellow-400">{selectedCall.model || 'unknown'}</code>
                  </div>
                  <div>
                    <span className="text-xs text-gray-500">Stop </span>
                    <code className="text-gray-300">{selectedCall.stopReason}</code>
                  </div>
                  <div>
                    <span className="text-xs text-gray-500">Tokens </span>
                    <span className="text-green-400">{selectedCall.inputTokens.toLocaleString()}</span>
                    <span className="text-gray-500"> / </span>
                    <span className="text-blue-400">{selectedCall.outputTokens.toLocaleString()}</span>
                  </div>
                  {selectedCall.durationMs > 0 && (
                    <div>
                      <span className="text-xs text-gray-500">Duration </span>
                      <code className="text-gray-300">{(selectedCall.durationMs / 1000).toFixed(2)}s</code>
                    </div>
                  )}
                </div>

                {/* Request section */}
                <div className="text-xs font-medium text-cyan-400 mt-3 mb-1 uppercase tracking-wide">Request</div>

                <DebugSection title="System Prompt" defaultOpen>
                  <pre className="text-gray-300 whitespace-pre-wrap text-xs max-h-40 overflow-auto">
                    {selectedCall.systemPrompt || '(empty)'}
                  </pre>
                </DebugSection>

                <DebugSection title={`Messages (${selectedCall.messagesSent.length})`}>
                  <div className="space-y-2 max-h-60 overflow-auto">
                    {selectedCall.messagesSent.map((msg, i) => (
                      <div key={i} className="border-l-2 border-gray-600 pl-3">
                        <div className="text-xs text-gray-500 mb-1">{msg.role}</div>
                        <pre className="text-gray-300 whitespace-pre-wrap text-xs">
                          {typeof msg.content === 'string'
                            ? msg.content.slice(0, 500)
                            : JSON.stringify(msg.content, null, 2).slice(0, 500)}
                        </pre>
                      </div>
                    ))}
                    {selectedCall.messagesSent.length === 0 && (
                      <div className="text-gray-500 text-xs italic">No messages</div>
                    )}
                  </div>
                </DebugSection>

                {selectedCall.toolsAvailable && (
                  <DebugSection title={`Tools (${selectedCall.toolsAvailable.length})`}>
                    <pre className="text-gray-300 text-xs overflow-auto max-h-40">
                      {JSON.stringify(selectedCall.toolsAvailable, null, 2)}
                    </pre>
                  </DebugSection>
                )}

                {/* Response section */}
                <div className="text-xs font-medium text-cyan-400 mt-3 mb-1 uppercase tracking-wide">Response</div>

                <DebugSection title="Response Content" defaultOpen>
                  <pre className="text-gray-300 text-xs overflow-auto max-h-60">
                    {JSON.stringify(selectedCall.responseContent, null, 2)}
                  </pre>
                </DebugSection>

                {selectedCall.toolCalls.length > 0 && (
                  <DebugSection title={`Tool Calls (${selectedCall.toolCalls.length})`} defaultOpen>
                    <div className="space-y-2 max-h-60 overflow-auto">
                      {selectedCall.toolCalls.map((tc, i) => (
                        <div key={i} className="border-l-2 border-yellow-600 pl-3">
                          <div className="text-xs text-yellow-400 font-mono mb-1">{tc.name}</div>
                          <div className="text-xs text-gray-500 mb-0.5">Input:</div>
                          <pre className="text-gray-300 text-xs mb-1">
                            {JSON.stringify(tc.input, null, 2).slice(0, 300)}
                          </pre>
                          <div className="text-xs text-gray-500 mb-0.5">Result:</div>
                          <pre className="text-gray-300 text-xs">
                            {typeof tc.result === 'string'
                              ? tc.result.slice(0, 300)
                              : JSON.stringify(tc.result, null, 2).slice(0, 300)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </DebugSection>
                )}
              </>
            ) : detailMessage?.request_debug ? (
              <>
                <div className="text-xs text-gray-500 mb-1">
                  Turn {detailMessage.turn}
                </div>

                {/* Summary row */}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  <div>
                    <span className="text-xs text-gray-500">Model </span>
                    <code className="text-yellow-400">{detailMessage.request_debug.model}</code>
                  </div>
                  {detailMessage.request_debug.worker_id && (
                    <div>
                      <span className="text-xs text-gray-500">Worker </span>
                      <button
                        onClick={() => onOpenWorker?.(detailMessage.request_debug!.worker_id!)}
                        className="inline-flex items-center gap-1 text-purple-400 hover:text-purple-300 transition-colors"
                      >
                        <Server className="w-3 h-3" />
                        {detailMessage.request_debug.worker_name || detailMessage.request_debug.worker_id.slice(0, 8)}
                      </button>
                    </div>
                  )}
                  {detailMessage.usage && (
                    <div>
                      <span className="text-xs text-gray-500">Tokens </span>
                      <span className="text-green-400">{detailMessage.usage.input_tokens.toLocaleString()}</span>
                      <span className="text-gray-500"> / </span>
                      <span className="text-blue-400">{detailMessage.usage.output_tokens.toLocaleString()}</span>
                    </div>
                  )}
                  {detailMessage.request_debug.iterations !== undefined && (
                    <div>
                      <span className="text-xs text-gray-500">Iterations </span>
                      <code className="text-purple-400">{detailMessage.request_debug.iterations}</code>
                    </div>
                  )}
                </div>

                {/* Request section */}
                <div className="text-xs font-medium text-cyan-400 mt-3 mb-1 uppercase tracking-wide">Request</div>

                <DebugSection title="System Prompt" defaultOpen>
                  <pre className="text-gray-300 whitespace-pre-wrap text-xs max-h-40 overflow-auto">
                    {detailMessage.request_debug.system}
                  </pre>
                </DebugSection>

                {detailMessage.request_debug.messages.length > 0 && (
                  <DebugSection title={`Messages (${detailMessage.request_debug.messages.length})`}>
                    <div className="space-y-2 max-h-60 overflow-auto">
                      {detailMessage.request_debug.messages.map((msg, i) => (
                        <div key={i} className="border-l-2 border-gray-600 pl-3">
                          <div className="text-xs text-gray-500 mb-1">{msg.role}</div>
                          <pre className="text-gray-300 whitespace-pre-wrap text-xs">
                            {typeof msg.content === 'string'
                              ? msg.content.slice(0, 500)
                              : JSON.stringify(msg.content, null, 2).slice(0, 500)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </DebugSection>
                )}

                {detailMessage.request_debug.tools && (
                  <DebugSection title={`Tools (${detailMessage.request_debug.tools.length})`}>
                    <pre className="text-gray-300 text-xs overflow-auto max-h-40">
                      {JSON.stringify(detailMessage.request_debug.tools, null, 2)}
                    </pre>
                  </DebugSection>
                )}

                {/* Response section */}
                <div className="text-xs font-medium text-cyan-400 mt-3 mb-1 uppercase tracking-wide">Response</div>

                <DebugSection title="Raw Response">
                  <pre className="text-gray-300 text-xs overflow-auto max-h-60">
                    {JSON.stringify(detailMessage.response_raw, null, 2)}
                  </pre>
                </DebugSection>
              </>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                Select a turn to view details
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function NewTaskModal({ onClose }: NewTaskModalProps) {
  const [namespaceId, setNamespaceId] = useState('');
  const [projectId, setProjectId] = useState('');
  const [namespaces, setNamespaces] = useState<Namespace[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingNamespaces, setLoadingNamespaces] = useState(true);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  const [debugTurn, setDebugTurn] = useState<number | null>(null);
  const [turnCounter, setTurnCounter] = useState(0);
  const [activeUniverseId, setActiveUniverseId] = useState<string | null>(null);
  const [workerAddress, setWorkerAddress] = useState<string | null>(null);
  const [workerId, setWorkerId] = useState<string | null>(null);
  const [workerName, setWorkerName] = useState<string | null>(null);
  const [workerModalData, setWorkerModalData] = useState<Worker | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Connect to the agent stream for the active universe
  const { events, lastResponse, agentInfo, llmCalls, doneSnapshot } =
    useAgentStream(activeUniverseId);

  // When the agent is done, build the assistant message from the done snapshot
  // (snapshot is captured from refs, guaranteed consistent even if React state is stale)
  useEffect(() => {
    if (!doneSnapshot || !activeUniverseId) return;

    const snap = doneSnapshot;
    // Collect all llm_response text from snapshot events
    const llmEvents = snap.events.filter((e) => e.type === 'llm_response');
    const finalText =
      llmEvents.length > 0
        ? (llmEvents[llmEvents.length - 1].data.text as string) || ''
        : snap.lastResponse || '(No response)';

    const newTurn = turnCounter + 1;
    setTurnCounter(newTurn);

    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: snap.error || finalText,
      timestamp: new Date(),
      turn: newTurn,
      usage: {
        input_tokens: snap.agentInfo.totalInputTokens,
        output_tokens: snap.agentInfo.totalOutputTokens,
      },
      request_debug: {
        endpoint: `worker://${workerAddress || 'unknown'}/launch`,
        model: snap.agentInfo.model || 'unknown',
        system: snap.llmCalls.length > 0 ? snap.llmCalls[0].systemPrompt : '(streamed - not available)',
        messages: snap.llmCalls.length > 0 ? snap.llmCalls[0].messagesSent : [],
        tools: snap.agentInfo.tools,
        thinking: null,
        max_tokens: 4096,
        iterations: snap.agentInfo.llmCallCount,
        worker_id: workerId || undefined,
        worker_name: workerName || undefined,
      },
      response_raw: { events: snap.events.map((e) => ({ type: e.type, data: e.data, timestamp: e.timestamp })) },
      llmCalls: snap.llmCalls,
    };

    setMessages((prev) => [...prev, assistantMessage]);
    setActiveUniverseId(null);
    setWorkerAddress(null);
    setWorkerId(null);
    setWorkerName(null);
    setIsLoading(false);
  }, [doneSnapshot]);

  // Filter projects by selected namespace
  const filteredProjects = namespaceId
    ? projects.filter((p) => p.namespace_id === namespaceId)
    : projects;

  // Calculate total tokens
  const totalTokens = messages.reduce(
    (acc, m) => ({
      input: acc.input + (m.usage?.input_tokens || 0),
      output: acc.output + (m.usage?.output_tokens || 0),
    }),
    { input: 0, output: 0 }
  );

  // Fetch namespaces on mount
  useEffect(() => {
    async function fetchNamespaces() {
      try {
        const res = await fetch(`${API_BASE}/organization/namespaces`);
        if (!res.ok) throw new Error('Failed to fetch namespaces');
        const data = await res.json();
        setNamespaces(data);
      } catch (e) {
        console.error('Failed to fetch namespaces:', e);
      } finally {
        setLoadingNamespaces(false);
      }
    }
    fetchNamespaces();
  }, []);

  // Fetch projects on mount
  useEffect(() => {
    async function fetchProjects() {
      try {
        const res = await fetch(`${API_BASE}/projects?status=active`);
        if (!res.ok) throw new Error('Failed to fetch projects');
        const data = await res.json();
        setProjects(data);
      } catch (e) {
        console.error('Failed to fetch projects:', e);
      } finally {
        setLoadingProjects(false);
      }
    }
    fetchProjects();
  }, []);

  // Clear project selection when namespace changes if project is not in new namespace
  useEffect(() => {
    if (namespaceId && projectId) {
      const project = projects.find((p) => p.id === projectId);
      if (project && project.namespace_id !== namespaceId) {
        setProjectId('');
      }
    }
  }, [namespaceId, projectId, projects]);

  // Focus input after projects load
  useEffect(() => {
    if (!loadingProjects) {
      inputRef.current?.focus();
    }
  }, [loadingProjects]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, agentInfo.currentTurn]);

  // Handle keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        if (showDebug) {
          setShowDebug(false);
        } else {
          onClose();
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, showDebug]);

  function getSelectedProject() {
    return projects.find((p) => p.id === projectId) || null;
  }

  function getSelectedNamespace() {
    return namespaces.find((n) => n.id === namespaceId) || null;
  }

  async function handleOpenWorker(wId: string) {
    try {
      const res = await fetch(`${API_BASE}/api/workers/${wId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setShowDebug(false);
      setWorkerModalData(data);
    } catch (e) {
      console.error('Failed to fetch worker:', e);
    }
  }

  async function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const selectedProject = getSelectedProject();
    const selectedNamespace = getSelectedNamespace();
    const context = {
      type: 'task' as const,
      namespaceId: namespaceId || null,
      namespaceName: selectedNamespace?.name || null,
      projectId: projectId || null,
      projectName: selectedProject?.name || null,
    };

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Launch a universe via the dispatch endpoint
      const res = await fetch(`${API_BASE}/api/universes/launch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: userMessage.content,
          context,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      // Activate the agent stream for this universe
      setWorkerAddress(data.worker_address || null);
      setWorkerId(data.worker_id || null);
      setWorkerName(data.worker_name || null);
      setActiveUniverseId(data.universe_id);
      // isLoading stays true — cleared when agent_done fires via useAgentStream
    } catch (e) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Error: ${e instanceof Error ? e.message : 'Failed to launch universe'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setIsLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  const hasDebugData = messages.some((m) => m.request_debug);

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="absolute inset-0 bg-black/60" onClick={onClose} />
        <div className="relative bg-gray-800 rounded-lg border border-gray-700 w-3/4 h-3/4 mx-4 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-700">
            <div className="flex items-center gap-4">
              <h3 className="text-lg font-medium text-gray-200">New Task</h3>
              {/* Counters */}
              {(totalTokens.input > 0 || totalTokens.output > 0) && (
                <div className="flex items-center gap-3 text-xs">
                  <span className="text-orange-400">turns: {turnCounter}</span>
                  <span className="text-gray-400">tokens: {totalTokens.input.toLocaleString()} | {totalTokens.output.toLocaleString()}</span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              {(hasDebugData || activeUniverseId) && (
                <button
                  onClick={() => setShowDebug(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs text-gray-400 hover:text-gray-200 hover:bg-gray-700"
                >
                  {activeUniverseId && isLoading && (
                    <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                  )}
                  <Code className="w-3.5 h-3.5" />
                  Debug
                </button>
              )}
              <button
                onClick={onClose}
                className="p-1 hover:bg-gray-700 rounded"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
          </div>

          {/* Main Content Area */}
          <div className="flex-1 flex overflow-hidden">
            {/* Chat Area - 3/4 width */}
            <div className="flex-1 flex flex-col">
              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && (
                  <div className="text-center text-gray-500 py-8">
                    <p>Describe the task you want to create...</p>
                  </div>
                )}
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg px-4 py-2 ${
                        message.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-700 text-gray-200'
                      }`}
                    >
                      <pre className="whitespace-pre-wrap font-sans text-sm">
                        {message.content}
                      </pre>
                      {/* Footer for assistant messages */}
                      {message.role === 'assistant' && (message.usage || message.turn) && (
                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-600">
                          <div className="flex items-center gap-3 text-xs text-gray-400">
                            {message.turn && (
                              <span className="text-orange-400">turn {message.turn}</span>
                            )}
                            {message.usage && (
                              <span>
                                {message.usage.input_tokens.toLocaleString()} | {message.usage.output_tokens.toLocaleString()} tok
                              </span>
                            )}
                            {message.request_debug?.iterations !== undefined && (
                              <span className="text-purple-400">
                                {message.request_debug.iterations} iter
                              </span>
                            )}
                          </div>
                          {message.request_debug && (
                            <button
                              onClick={() => {
                                setDebugTurn(message.turn ?? null);
                                setShowDebug(true);
                              }}
                              className="text-xs text-gray-500 hover:text-gray-300 ml-2"
                            >
                              debug
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="max-w-[80%] bg-gray-700 text-gray-200 rounded-lg px-4 py-2">
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                        <span className="animate-pulse">Thinking...</span>
                      </div>
                      {lastResponse && activeUniverseId && (
                        <pre className="whitespace-pre-wrap font-sans text-sm mt-1">
                          {lastResponse.slice(0, 300)}
                          {lastResponse.length > 300 && '...'}
                        </pre>
                      )}
                      {/* Live footer — same format as completed message footer */}
                      <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-600">
                        <div className="flex items-center gap-3 text-xs text-gray-400">
                          {agentInfo.currentTurn > 0 && (
                            <span className="text-orange-400">turn {agentInfo.currentTurn}</span>
                          )}
                          <span>
                            {agentInfo.totalInputTokens.toLocaleString()} | {agentInfo.totalOutputTokens.toLocaleString()} tok
                          </span>
                          <span className="text-purple-400">
                            {agentInfo.llmCallCount} iter
                          </span>
                        </div>
                        <button
                          onClick={() => setShowDebug(true)}
                          className="text-xs text-gray-500 hover:text-gray-300 ml-2"
                        >
                          debug
                        </button>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <form onSubmit={handleSubmit} className="p-4 border-t border-gray-700">
                <div className="flex gap-2">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Describe the task..."
                    rows={2}
                    className="flex-1 px-3 py-2 bg-gray-900 border border-gray-600 rounded text-gray-200 text-sm focus:outline-none focus:border-blue-500 resize-none"
                  />
                  <button
                    type="submit"
                    disabled={!input.trim() || isLoading}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-white disabled:opacity-50 disabled:cursor-not-allowed self-end"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Enter to send, Shift+Enter for new line, Esc to close
                </div>
              </form>
            </div>

            {/* Right Sidebar - 1/4 width */}
            <div className="w-64 border-l border-gray-700 p-4 space-y-4 overflow-y-auto">
              <h4 className="text-sm font-medium text-gray-300">Details</h4>

              {/* Namespace */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Namespace</label>
                {loadingNamespaces ? (
                  <div className="text-xs text-gray-500">Loading...</div>
                ) : (
                  <div className="relative">
                    <select
                      value={namespaceId}
                      onChange={(e) => setNamespaceId(e.target.value)}
                      className="w-full pl-2 pr-7 py-1.5 bg-gray-900 border border-gray-600 rounded text-gray-200 text-xs appearance-none focus:outline-none focus:border-blue-500"
                    >
                      <option value="">All namespaces</option>
                      {namespaces.map((ns) => (
                        <option key={ns.id} value={ns.id}>
                          {ns.name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-400 pointer-events-none" />
                  </div>
                )}
              </div>

              {/* Project */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Project</label>
                {loadingProjects ? (
                  <div className="text-xs text-gray-500">Loading...</div>
                ) : (
                  <div className="relative">
                    <select
                      value={projectId}
                      onChange={(e) => setProjectId(e.target.value)}
                      className="w-full pl-2 pr-7 py-1.5 bg-gray-900 border border-gray-600 rounded text-gray-200 text-xs appearance-none focus:outline-none focus:border-blue-500"
                    >
                      <option value="">-- Optional --</option>
                      {filteredProjects.map((project) => (
                        <option key={project.id} value={project.id}>
                          {project.name}
                          {!namespaceId && project.namespace && ` (${project.namespace.name})`}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-400 pointer-events-none" />
                  </div>
                )}
                {namespaceId && filteredProjects.length === 0 && (
                  <div className="text-xs text-gray-500 mt-1">
                    No projects in this namespace
                  </div>
                )}
              </div>

              {/* Context Summary */}
              <div className="pt-4 border-t border-gray-700">
                <div className="text-xs text-gray-500">
                  {getSelectedNamespace() && (
                    <div className="mb-1">
                      <span className="text-gray-400">Namespace:</span> {getSelectedNamespace()?.name}
                    </div>
                  )}
                  {getSelectedProject() && (
                    <div>
                      <span className="text-gray-400">Project:</span> {getSelectedProject()?.name}
                    </div>
                  )}
                  {!getSelectedNamespace() && !getSelectedProject() && (
                    <div className="text-gray-500 italic">No context selected</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Debug Panel */}
      {showDebug && (
        <DebugPanel
          messages={messages}
          initialTurn={debugTurn}
          onClose={() => { setShowDebug(false); setDebugTurn(null); }}
          onOpenWorker={handleOpenWorker}
          liveEvents={activeUniverseId ? events : undefined}
          isStreaming={!!activeUniverseId && isLoading}
          streamingAgentInfo={activeUniverseId ? agentInfo : undefined}
          liveLlmCalls={activeUniverseId ? llmCalls : undefined}
        />
      )}

      {/* Worker Detail Modal (opened from debug panel) */}
      {workerModalData && (
        <WorkerDetailModal
          worker={workerModalData}
          universes={[]}
          events={[]}
          onClose={() => setWorkerModalData(null)}
        />
      )}
    </>
  );
}
