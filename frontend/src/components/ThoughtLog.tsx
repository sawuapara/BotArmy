import { useEffect, useRef } from 'react';
import { Brain } from 'lucide-react';

interface ThoughtLogProps {
  thoughts: string[];
}

export function ThoughtLog({ thoughts }: ThoughtLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new thoughts come in
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thoughts]);

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 h-full flex flex-col">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-700">
        <Brain className="w-5 h-5 text-purple-400" />
        <h3 className="font-semibold text-gray-200">Chain of Thought</h3>
        <span className="text-xs text-gray-500">({thoughts.length} entries)</span>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-sm"
      >
        {thoughts.length === 0 ? (
          <div className="text-gray-500 text-center py-4">
            Waiting for orchestrator to start...
          </div>
        ) : (
          thoughts.map((thought, index) => (
            <div
              key={index}
              className="p-3 bg-gray-900 rounded border-l-2 border-purple-500 whitespace-pre-wrap"
            >
              <span className="text-gray-500 text-xs">#{index + 1}</span>
              <p className="text-gray-300 mt-1">{thought}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
