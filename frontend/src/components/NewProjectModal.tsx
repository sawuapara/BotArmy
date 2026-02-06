import { useState, useEffect, useRef } from 'react';
import { X, Send, ChevronDown, Code, ChevronRight } from 'lucide-react';
import { API_BASE } from '../lib/config';

interface Namespace {
  id: string;
  name: string;
}

interface ApiDebugInfo {
  endpoint: string;
  model: string;
  system: string;
  messages: Array<{ role: string; content: string }>;
  tools: unknown[] | null;
  thinking: unknown | null;
  max_tokens: number;
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
  usage?: UsageInfo;
  request_debug?: ApiDebugInfo;
  response_raw?: unknown;
}

interface NewProjectModalProps {
  onClose: () => void;
  onProjectCreated?: (project: { id: string; name: string }) => void;
  defaultNamespaceId?: string;
}

// Debug Panel Component
function DebugPanel({
  message,
  onClose,
}: {
  message: Message;
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState<'request' | 'response'>('request');

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative bg-gray-900 rounded-lg border border-gray-600 w-3/4 h-3/4 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-gray-700">
          <div className="flex items-center gap-4">
            <h3 className="text-sm font-medium text-gray-200">API Debug</h3>
            {message.usage && (
              <div className="flex items-center gap-3 text-xs">
                <span className="text-green-400">
                  In: {message.usage.input_tokens.toLocaleString()}
                </span>
                <span className="text-blue-400">
                  Out: {message.usage.output_tokens.toLocaleString()}
                </span>
                <span className="text-gray-400">
                  Total: {(message.usage.input_tokens + message.usage.output_tokens).toLocaleString()}
                </span>
              </div>
            )}
          </div>
          <button onClick={onClose} className="p-1 hover:bg-gray-700 rounded">
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-700">
          <button
            onClick={() => setActiveTab('request')}
            className={`px-4 py-2 text-sm ${
              activeTab === 'request'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            Request
          </button>
          <button
            onClick={() => setActiveTab('response')}
            className={`px-4 py-2 text-sm ${
              activeTab === 'response'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            Response
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {activeTab === 'request' && message.request_debug && (
            <div className="space-y-4">
              <DebugSection title="Model" defaultOpen>
                <code className="text-yellow-400">{message.request_debug.model}</code>
                <span className="text-gray-500 ml-2">
                  (max_tokens: {message.request_debug.max_tokens})
                </span>
              </DebugSection>

              <DebugSection title="Endpoint" defaultOpen>
                <code className="text-green-400">{message.request_debug.endpoint}</code>
              </DebugSection>

              <DebugSection title="System Prompt" defaultOpen>
                <pre className="text-gray-300 whitespace-pre-wrap text-xs">
                  {message.request_debug.system}
                </pre>
              </DebugSection>

              <DebugSection title="Messages" defaultOpen>
                <div className="space-y-2">
                  {message.request_debug.messages.map((msg, i) => (
                    <div key={i} className="border-l-2 border-gray-600 pl-3">
                      <div className="text-xs text-gray-500 mb-1">{msg.role}</div>
                      <pre className="text-gray-300 whitespace-pre-wrap text-xs">
                        {msg.content}
                      </pre>
                    </div>
                  ))}
                </div>
              </DebugSection>

              {message.request_debug.tools && (
                <DebugSection title="Tools">
                  <pre className="text-gray-300 text-xs overflow-auto">
                    {JSON.stringify(message.request_debug.tools, null, 2)}
                  </pre>
                </DebugSection>
              )}

              {message.request_debug.thinking && (
                <DebugSection title="Thinking">
                  <pre className="text-gray-300 text-xs overflow-auto">
                    {JSON.stringify(message.request_debug.thinking, null, 2)}
                  </pre>
                </DebugSection>
              )}
            </div>
          )}

          {activeTab === 'response' && message.response_raw && (
            <div className="space-y-4">
              <DebugSection title="Raw Response" defaultOpen>
                <pre className="text-gray-300 text-xs overflow-auto">
                  {JSON.stringify(message.response_raw, null, 2)}
                </pre>
              </DebugSection>
            </div>
          )}
        </div>
      </div>
    </div>
  );
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

export function NewProjectModal({ onClose, onProjectCreated, defaultNamespaceId }: NewProjectModalProps) {
  const [namespaceId, setNamespaceId] = useState(defaultNamespaceId || '');
  const [namespaces, setNamespaces] = useState<Namespace[]>([]);
  const [loadingNamespaces, setLoadingNamespaces] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [debugMessage, setDebugMessage] = useState<Message | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
        // Set default namespace if not already set
        if (!namespaceId && data.length > 0) {
          setNamespaceId(data[0].id);
        }
      } catch (e) {
        console.error('Failed to fetch namespaces:', e);
      } finally {
        setLoadingNamespaces(false);
      }
    }
    fetchNamespaces();
  }, [namespaceId]);

  // Focus input after namespaces load
  useEffect(() => {
    if (!loadingNamespaces) {
      inputRef.current?.focus();
    }
  }, [loadingNamespaces]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        if (debugMessage) {
          setDebugMessage(null);
        } else {
          onClose();
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, debugMessage]);

  function getSelectedNamespace() {
    return namespaces.find((n) => n.id === namespaceId) || null;
  }

  async function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const selectedNamespace = getSelectedNamespace();
    const context = {
      type: 'project' as const,
      namespaceId: namespaceId || null,
      namespaceName: selectedNamespace?.name || null,
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

    // Build history from previous messages
    const history = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage.content,
          context,
          history,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.message,
        timestamp: new Date(),
        usage: data.usage,
        request_debug: data.request_debug,
        response_raw: data.response_raw,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (e) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Error: ${e instanceof Error ? e.message : 'Failed to get response'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="absolute inset-0 bg-black/60" onClick={onClose} />
        <div className="relative bg-gray-800 rounded-lg border border-gray-700 w-3/4 h-3/4 mx-4 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-700">
            <div className="flex items-center gap-4">
              <h3 className="text-lg font-medium text-gray-200">New Project</h3>
              {/* Token Counter */}
              {(totalTokens.input > 0 || totalTokens.output > 0) && (
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span className="text-green-400">{totalTokens.input.toLocaleString()} in</span>
                  <span className="text-blue-400">{totalTokens.output.toLocaleString()} out</span>
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-700 rounded"
            >
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>

          {/* Main Content Area */}
          <div className="flex-1 flex overflow-hidden">
            {/* Chat Area - 3/4 width */}
            <div className="flex-1 flex flex-col">
              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && (
                  <div className="text-center text-gray-500 py-8">
                    <p>Describe the project you want to create...</p>
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
                      {/* Debug button for assistant messages */}
                      {message.role === 'assistant' && message.request_debug && (
                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-600">
                          <div className="text-xs text-gray-400">
                            {message.usage && (
                              <span>
                                {message.usage.input_tokens} / {message.usage.output_tokens} tokens
                              </span>
                            )}
                          </div>
                          <button
                            onClick={() => setDebugMessage(message)}
                            className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-200"
                          >
                            <Code className="w-3 h-3" />
                            Debug
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="bg-gray-700 text-gray-200 rounded-lg px-4 py-2">
                      <span className="animate-pulse">Thinking...</span>
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
                    placeholder="Describe the project..."
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

              {/* Context Summary */}
              <div className="pt-4 border-t border-gray-700">
                <div className="text-xs text-gray-500">
                  {getSelectedNamespace() && (
                    <div className="mb-1">
                      <span className="text-gray-400">Namespace:</span> {getSelectedNamespace()?.name}
                    </div>
                  )}
                  {!getSelectedNamespace() && (
                    <div className="text-gray-500 italic">No namespace selected</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Debug Panel */}
      {debugMessage && (
        <DebugPanel message={debugMessage} onClose={() => setDebugMessage(null)} />
      )}
    </>
  );
}
