import React, { useState, useEffect, useMemo } from 'react';
import {
  Layers,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  AlertTriangle,
  FileCode,
  Box,
  FunctionSquare,
  Sparkles,
  Search,
  Code2,
  Share2,
  Check
} from 'lucide-react';


import { useEditor } from '../../core/editor/EditorContext';
import { useAI } from '../../core/ai/AIContext';

interface GraphNode {
  id: string;
  label: string;
  path: string;
  type: string;
  extension: string;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  circular_imports: string[][];
  summary: {
    total_nodes: number;
    total_edges: number;
    circular_count: number;
  };
}

export const VisualWorkspaceGraph: React.FC = () => {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [highlightCircular, setHighlightCircular] = useState(false);
  const [copiedMermaid, setCopiedMermaid] = useState(false);

  const { handleSelectFile } = useEditor();
  const { handleSendMessage } = useAI();

  const fetchGraph = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/workspace/graph', {
        headers: { Authorization: `Bearer ${localStorage.getItem('session_token') || ''}` }
      });
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (e) {
      console.error('Failed to fetch workspace graph:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, []);

  const handleExplainGraph = () => {
    if (!data) return;
    const prompt = `Analyse our workspace architecture graph:\n- Total Files: ${data.summary.total_nodes}\n- Total Dependencies: ${data.summary.total_edges}\n- Circular Imports: ${data.summary.circular_count}\n\nProvide an architectural review and suggest structural improvements.`;
    handleSendMessage(prompt, 'Agent', false);
  };

  const mermaidDiagram = useMemo(() => {
    if (!data || data.nodes.length === 0) return '';
    let graphStr = 'graph TD\n';
    data.nodes.slice(0, 25).forEach(node => {
      const cleanLabel = node.label.replace(/[^a-zA-Z0-9_]/g, '_');
      graphStr += `  ${cleanLabel}["${node.label}"]\n`;
    });
    data.edges.slice(0, 30).forEach(edge => {
      const srcNode = data.nodes.find(n => n.id === edge.source);
      const tgtNode = data.nodes.find(n => n.id === edge.target);
      if (srcNode && tgtNode) {
        const srcLabel = srcNode.label.replace(/[^a-zA-Z0-9_]/g, '_');
        const tgtLabel = tgtNode.label.replace(/[^a-zA-Z0-9_]/g, '_');
        graphStr += `  ${srcLabel} --> ${tgtLabel}\n`;
      }
    });
    return graphStr;
  }, [data]);

  const handleCopyMermaid = () => {
    if (!mermaidDiagram) return;
    navigator.clipboard.writeText(mermaidDiagram);
    setCopiedMermaid(true);
    setTimeout(() => setCopiedMermaid(false), 2000);
  };

  const filteredNodes = useMemo(() => {
    if (!data) return [];
    return data.nodes.filter(n => {
      const matchesSearch = !searchQuery || 
        n.label.toLowerCase().includes(searchQuery.toLowerCase()) || 
        n.path.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesType = filterType === 'all' || n.type === filterType;
      return matchesSearch && matchesType;
    });
  }, [data, searchQuery, filterType]);

  const connectedNodes = useMemo(() => {
    if (!selectedNode || !data) return { imports: [], importedBy: [] };
    const imports = data.edges
      .filter(e => e.source === selectedNode.id)
      .map(e => data.nodes.find(n => n.id === e.target))
      .filter((n): n is GraphNode => Boolean(n));

    const importedBy = data.edges
      .filter(e => e.target === selectedNode.id)
      .map(e => data.nodes.find(n => n.id === e.source))
      .filter((n): n is GraphNode => Boolean(n));

    return { imports, importedBy };
  }, [selectedNode, data]);

  return (
    <div className="h-full flex flex-col bg-[#0d0e15] text-xs font-sans overflow-hidden border border-white/10 rounded-xl p-3 space-y-3">
      {/* ── Graph Header & Controls ── */}
      <div className="flex items-center justify-between pb-2 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <div>
            <h4 className="font-bold text-white text-xs">Visual Workspace Graph</h4>
            <p className="text-[10px] text-gray-400">
              {data?.summary.total_nodes || 0} modules · {data?.summary.total_edges || 0} import edges
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={handleCopyMermaid}
            className="flex items-center gap-1 text-[11px] font-semibold text-zinc-200 bg-white/5 hover:bg-white/10 border border-white/10 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
            title="Copy Mermaid Architecture Diagram"
          >
            {copiedMermaid ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Share2 className="w-3.5 h-3.5 text-cyan-400" />}
            <span>{copiedMermaid ? 'Copied' : 'Mermaid'}</span>
          </button>

          <button
            onClick={handleExplainGraph}
            className="flex items-center gap-1 text-[11px] font-bold text-white bg-violet-600 hover:bg-violet-500 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
            title="AI Architecture Explanation"
          >
            <Sparkles className="w-3.5 h-3.5 fill-current text-amber-300" /> AI Explain
          </button>

          <button
            onClick={() => setHighlightCircular(!highlightCircular)}
            className={`p-1.5 rounded-lg border text-xs transition-colors cursor-pointer ${
              highlightCircular
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                : 'bg-white/5 text-gray-400 border-white/10 hover:text-white'
            }`}
            title="Highlight Circular Imports"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={fetchGraph}
            disabled={loading}
            className="p-1.5 text-gray-400 hover:text-white bg-white/5 border border-white/10 rounded-lg transition-colors cursor-pointer disabled:opacity-40"
            title="Refresh Graph"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* ── Search & Module Type Filter ── */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Filter graph nodes..."
            className="w-full bg-black/40 border border-white/10 rounded-lg pl-8 pr-2 py-1.5 text-xs text-white placeholder-gray-500 outline-none focus:border-cyan-500/50 font-mono"
          />
        </div>

        <div className="flex bg-black/40 border border-white/10 p-0.5 rounded-lg text-[10px] font-semibold">
          {['all', 'component', 'context', 'api', 'file'].map(type => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`px-2 py-0.5 rounded capitalize transition-colors cursor-pointer ${
                filterType === type ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-gray-400 hover:text-white'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* ── Circular Imports Alert ── */}
      {data && data.circular_imports.length > 0 && (
        <div className="bg-amber-500/10 border border-amber-500/30 p-2 rounded-lg text-[11px] text-amber-300 flex items-center justify-between">
          <span className="flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            Detected {data.circular_imports.length} circular import chain(s)
          </span>
          <button
            onClick={() => setHighlightCircular(true)}
            className="text-[10px] underline font-bold hover:text-white cursor-pointer"
          >
            Highlight
          </button>
        </div>
      )}

      {/* ── Selected Node Inspector Panel ── */}
      {selectedNode && (
        <div className="p-2.5 bg-zinc-950 border border-cyan-500/30 rounded-xl space-y-1.5 text-[10.5px]">
          <div className="flex items-center justify-between">
            <span className="font-bold text-white flex items-center gap-1.5">
              <Code2 className="w-3.5 h-3.5 text-cyan-400" />
              {selectedNode.label}
            </span>
            <span className="text-[9px] font-mono text-zinc-400 uppercase bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
              {selectedNode.type}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[10px]">
            <div className="bg-zinc-900/60 p-1.5 rounded-lg border border-zinc-800/80">
              <span className="text-violet-400 font-semibold block mb-0.5">Imports ({connectedNodes.imports.length})</span>
              {connectedNodes.imports.length === 0 ? (
                <span className="text-zinc-600 italic">No internal imports</span>
              ) : (
                connectedNodes.imports.map(n => (
                  <div key={n.id} className="text-zinc-300 truncate hover:text-white cursor-pointer" onClick={() => handleSelectFile(n.path)}>
                    → {n.label}
                  </div>
                ))
              )}
            </div>

            <div className="bg-zinc-900/60 p-1.5 rounded-lg border border-zinc-800/80">
              <span className="text-emerald-400 font-semibold block mb-0.5">Imported By ({connectedNodes.importedBy.length})</span>
              {connectedNodes.importedBy.length === 0 ? (
                <span className="text-zinc-600 italic">Root module / Entry point</span>
              ) : (
                connectedNodes.importedBy.map(n => (
                  <div key={n.id} className="text-zinc-300 truncate hover:text-white cursor-pointer" onClick={() => handleSelectFile(n.path)}>
                    ← {n.label}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Main Graphical Visualizer Canvas ── */}
      <div className="flex-1 bg-black/40 border border-white/5 rounded-xl overflow-hidden relative flex flex-col items-center justify-center min-h-[220px]">
        {loading ? (
          <div className="flex items-center gap-2 text-gray-400 text-xs">
            <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" /> Building AST Graph...
          </div>
        ) : filteredNodes.length === 0 ? (
          <div className="text-gray-500 text-xs italic">No nodes match your filter query.</div>
        ) : (
          <div className="w-full h-full p-4 overflow-auto grid grid-cols-2 md:grid-cols-3 gap-2 font-sans" style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
            {filteredNodes.map((node) => {
              const isSelected = selectedNode?.id === node.id;
              return (
                <div
                  key={node.id}
                  onClick={() => {
                    setSelectedNode(node);
                    handleSelectFile(node.path);
                  }}
                  className={`p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? 'bg-cyan-500/20 border-cyan-400 text-white shadow-lg ring-1 ring-cyan-500/50'
                      : 'bg-black/40 border-white/5 hover:border-white/20 text-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {node.type === 'component' && <Box className="w-4 h-4 text-emerald-400 shrink-0" />}
                    {node.type === 'context' && <Code2 className="w-4 h-4 text-purple-400 shrink-0" />}
                    {node.type === 'hook' && <FunctionSquare className="w-4 h-4 text-blue-400 shrink-0" />}
                    {node.type === 'api' && <FileCode className="w-4 h-4 text-amber-400 shrink-0" />}
                    {node.type === 'file' && <FileCode className="w-4 h-4 text-gray-400 shrink-0" />}
                    
                    <div className="min-w-0">
                      <span className="font-semibold text-xs text-white block truncate">{node.label}</span>
                      <span className="text-[9px] text-gray-500 block truncate font-mono">{node.path}</span>
                    </div>
                  </div>
                  <span className="text-[9px] uppercase font-mono px-1.5 py-0.5 rounded bg-white/5 text-gray-400 border border-white/5 shrink-0 ml-1">
                    {node.type}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Zoom Controls */}
        <div className="absolute bottom-3 right-3 flex items-center gap-1 bg-black/80 border border-white/10 p-1 rounded-lg">
          <button onClick={() => setZoom(z => Math.max(0.5, z - 0.1))} className="p-1 text-gray-400 hover:text-white cursor-pointer">
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="text-[10px] font-mono text-gray-400 px-1">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom(z => Math.min(2, z + 0.1))} className="p-1 text-gray-400 hover:text-white cursor-pointer">
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};

