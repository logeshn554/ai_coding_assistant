import { useState, useEffect } from 'react';
import { Beaker, Play, CheckCircle2, XCircle, AlertCircle, RefreshCw } from 'lucide-react';

export default function TestingSidebar() {
  const [tests, setTests] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [outcomes, setOutcomes] = useState<Record<string, 'passed' | 'failed' | null>>({});
  const [runLogs, setRunLogs] = useState<string | null>(null);

  const discoverTests = async () => {
    try {
      const res = await fetch('/api/testing/discover');
      const data = await res.json();
      setTests(data.tests || []);
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunAll = async () => {
    setRunning(true);
    setRunLogs(null);
    try {
      const res = await fetch('/api/testing/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file: null })
      });
      const data = await res.json();
      setRunLogs(data.output);
      
      const newOutcomes: Record<string, 'passed' | 'failed'> = {};
      tests.forEach(t => {
        newOutcomes[t] = data.passed ? 'passed' : 'failed';
      });
      setOutcomes(newOutcomes);
    } catch (e) {
      console.error(e);
    } finally {
      setRunning(false);
    }
  };

  const handleRunSingle = async (file: string) => {
    setRunning(true);
    setRunLogs(null);
    try {
      const res = await fetch('/api/testing/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file })
      });
      const data = await res.json();
      setRunLogs(data.output);
      setOutcomes(prev => ({
        ...prev,
        [file]: data.passed ? 'passed' : 'failed'
      }));
    } catch (e) {
      console.error(e);
    } finally {
      setRunning(false);
    }
  };



  useEffect(() => {
    discoverTests();
  }, []);

  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#cccccc] font-sans select-none">
      {/* Header */}
      <div className="px-3 py-1.5 border-b border-[#2d2d2d] bg-[#181818] flex items-center justify-between shrink-0">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
          <Beaker className="w-3.5 h-3.5 text-violet-400" />
          Test Explorer
        </span>
        <button
          onClick={discoverTests}
          className="text-[10px] text-violet-400 hover:text-violet-300 cursor-pointer"
          title="Refresh tests list"
        >
          Discover
        </button>
      </div>

      {/* Action buttons */}
      <div className="p-2 border-b border-[#2d2d2d] bg-[#131313] shrink-0 flex flex-col gap-2">
        <button
          onClick={handleRunAll}
          disabled={running || tests.length === 0}
          className="w-full py-1 bg-[#8b5cf6] hover:bg-[#7c4dff] disabled:opacity-40 text-white rounded-none text-[10px] font-semibold flex items-center justify-center gap-1 cursor-pointer border border-violet-500/20"
        >
          {running ? (
            <>
              <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Running tests...
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5" /> Run All Tests ({tests.length})
            </>
          )}
        </button>
      </div>

      {/* Tests feed list */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-3">
        {tests.length === 0 ? (
          <div className="py-8 text-center text-xs text-gray-500 italic">
            No test files discovered in this workspace.
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">
              Discovered Suites
            </div>
            <div className="space-y-1">
              {tests.map((testFile) => {
                const status = outcomes[testFile];
                return (
                  <div key={testFile} className="flex items-center justify-between p-1 bg-[#1e1e1e] hover:bg-white/5 border border-[#2d2d2d] rounded-none">
                    <div className="flex items-center gap-2 min-w-0">
                      {status === 'passed' ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-450 shrink-0" />
                      ) : status === 'failed' ? (
                        <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
                      ) : (
                        <AlertCircle className="w-3.5 h-3.5 text-gray-550 shrink-0" />
                      )}
                      <span className="text-[10px] text-gray-300 truncate font-mono" title={testFile}>
                        {testFile.split('/').pop()}
                      </span>
                    </div>
                    
                    <button
                      onClick={() => handleRunSingle(testFile)}
                      disabled={running}
                      className="p-1 hover:bg-white/5 text-gray-400 hover:text-white cursor-pointer rounded-none"
                      title="Run single test suite"
                    >
                      <Play className="w-3 h-3" />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Logs */}
        {runLogs && (
          <div className="space-y-2 pt-2 border-t border-[#2d2d2d] select-text">
            <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider select-none">
              Test Execution Output
            </div>
            <pre className="p-2 bg-[#131313] border border-[#2d2d2d] rounded-none font-mono text-[9px] text-gray-400 whitespace-pre-wrap max-h-48 overflow-y-auto pr-1 scrollbar-thin">
              {runLogs}
            </pre>
          </div>
        )}

      </div>
    </div>
  );
}