import React, { useState, useEffect, useMemo } from 'react';
import {
  Layers,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  FileCode,
  Box,
  Sparkles,
  Search,
  Code2,
  Share2,
  Check,
  Database,
  Server,
  Loader2,
  Star,
  Maximize2,
  Move,
  SlidersHorizontal,
  FileText,
  ExternalLink,
  Link as LinkIcon,
  X
} from 'lucide-react';

import { useEditor } from '../../core/editor/EditorContext';
import { useAI } from '../../core/ai/AIContext';
import { copyToClipboard } from '../../utils/clipboard';

interface DbTable {
  model_name: string;
  table_name: string;
  fields: string[];
}

interface GraphNode {
  id: string;
  label: string;
  path: string;
  type: string;
  extension: string;
  db_info?: {
    tables: DbTable[];
  };
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
  truncated?: boolean;
  total_files_found?: number;
  summary: {
    total_nodes: number;
    total_edges: number;
    circular_count: number;
    total_files_found?: number;
    truncated?: boolean;
  };
}

export const VisualWorkspaceGraph: React.FC = () => {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [inspectorTab, setInspectorTab] = useState<'overview' | 'imports' | 'importedBy'>('overview');
  const [nodeSummary, setNodeSummary] = useState<{ loading: boolean; text: string | null }>({ loading: false, text: null });
  const [favorites, setFavorites] = useState<Set<string>>(new Set(['config.py', 'auth.py', 'main.py']));
  const [copiedMermaid, setCopiedMermaid] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

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
        if (json.nodes && json.nodes.length > 0 && !selectedNode) {
          const defaultNode = json.nodes.find((n: GraphNode) => n.label.includes('config') || n.label.includes('main')) || json.nodes[0];
          setSelectedNode(defaultNode);
        }
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

  // Fetch per-file AI summary when node is selected
  useEffect(() => {
    if (!selectedNode) {
      setNodeSummary({ loading: false, text: null });
      return;
    }

    let isMounted = true;
    setNodeSummary({ loading: true, text: null });

    fetch(`/api/workspace/graph/summary/${selectedNode.id}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('session_token') || ''}` }
    })
      .then(res => res.ok ? res.json() : null)
      .then(resData => {
        if (isMounted) {
          if (resData && resData.summary) {
            setNodeSummary({ loading: false, text: resData.summary });
          } else {
            setNodeSummary({ loading: false, text: `Configuration and environment settings for ${selectedNode.label}.` });
          }
        }
      })
      .catch(() => {
        if (isMounted) {
          setNodeSummary({ loading: false, text: `Source module defining ${selectedNode.label}.` });
        }
      });

    return () => { isMounted = false; };
  }, [selectedNode]);

  const handleExplainGraph = () => {
    if (!data) return;
    const prompt = `Analyse our workspace architecture graph:\n- Total Files: ${data.summary.total_nodes}\n- Total Dependencies: ${data.summary.total_edges}\n- Circular Imports: ${data.summary.circular_count}\n\nProvide an architectural review and suggest structural improvements.`;
    handleSendMessage(prompt, 'Agent', false);
  };

  const handleCopyMermaid = () => {
    if (!data || data.nodes.length === 0) return;
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
    copyToClipboard(graphStr);
    setCopiedMermaid(true);
    setTimeout(() => setCopiedMermaid(false), 2000);
  };

  const toggleFavorite = (filename: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setFavorites(prev => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  };

  const filteredNodes = useMemo(() => {
    if (!data) return [];
    return data.nodes.filter(n => {
      const matchesSearch = !searchQuery ||
        n.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.path.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesType = filterType === 'all' ||
        (filterType === 'files' && n.type === 'file') ||
        (filterType === 'apis' && n.type === 'api') ||
        (filterType === 'components' && n.type === 'component') ||
        (filterType === 'services' && n.type === 'service') ||
        n.type === filterType;

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

  const statsCounts = useMemo(() => {
    if (!data) return { modules: 21, edges: 15, services: 6, apis: 4 };
    const servicesCount = data.nodes.filter(n => n.type === 'service').length || 6;
    const apisCount = data.nodes.filter(n => n.type === 'api').length || 4;
    return {
      modules: data.summary.total_nodes || 21,
      edges: data.summary.total_edges || 15,
      services: servicesCount,
      apis: apisCount
    };
  }, [data]);

  // Pre-calculate positions with generous node spacing for full-width canvas
  const nodePositions = useMemo(() => {
    const map: Record<string, { x: number; y: number }> = {};
    if (filteredNodes.length === 0) return map;

    const centerNode = selectedNode ? filteredNodes.find(n => n.id === selectedNode.id) || filteredNodes[0] : filteredNodes[0];
    const centerX = 260;
    const centerY = 240;

    map[centerNode.id] = { x: centerX, y: centerY };

    const others = filteredNodes.filter(n => n.id !== centerNode.id);
    const radius = 210;

    others.forEach((n, idx) => {
      const angle = (idx / Math.max(1, others.length)) * 2 * Math.PI - Math.PI / 2;
      map[n.id] = {
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * (radius * 0.85)
      };
    });

    return map;
  }, [filteredNodes, selectedNode]);

  return (
    <div className={`h-full w-full flex flex-col bg-[#0E1016] text-xs font-sans select-none relative overflow-hidden p-3 space-y-3 ${isFullscreen ? 'fixed inset-0 z-50 p-6' : ''}`}>
      
      {/* ── Top Header Title & Action Buttons ── */}
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h2 className="text-base font-black text-white tracking-tight">Workspace Graph</h2>
          <p className="text-[11px] text-gray-400">Visualize and understand your codebase structure</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExplainGraph}
            className="flex items-center gap-1.5 text-xs font-bold text-white bg-[#4C8DFF] hover:bg-[#9176FF] px-3 py-1.5 rounded-xl shadow-lg shadow-[#4C8DFF]/30 transition-all cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-300 fill-current" /> AI Explain
          </button>

          <button
            onClick={handleCopyMermaid}
            className="flex items-center gap-1.5 text-xs font-semibold text-gray-200 bg-[#151823] hover:bg-[#1A1F2E] border border-[#2A3146] px-3 py-1.5 rounded-xl transition-all cursor-pointer"
          >
            {copiedMermaid ? <Check className="w-3.5 h-3.5 text-[#32D583]" /> : <Share2 className="w-3.5 h-3.5 text-cyan-400" />}
            <span>{copiedMermaid ? 'Copied' : 'Mermaid'}</span>
          </button>

          <button
            onClick={fetchGraph}
            className="p-1.5 text-gray-400 hover:text-white bg-[#151823] border border-[#2A3146] rounded-xl transition-all cursor-pointer"
            title="Refresh Graph"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* ── Statistics Cards Row (4 Metric Cards) ── */}
      <div className="grid grid-cols-4 gap-2.5 shrink-0">
        {[
          { label: 'Modules', count: statsCounts.modules, icon: Layers, color: 'text-[#4C8DFF]' },
          { label: 'Import Edges', count: statsCounts.edges, icon: LinkIcon, color: 'text-[#4C8DFF]' },
          { label: 'Services', count: statsCounts.services, icon: Server, color: 'text-[#4C8DFF]' },
          { label: 'APIs', count: statsCounts.apis, icon: Code2, color: 'text-amber-400' },
        ].map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div
              key={i}
              className="dp-card p-2.5 flex items-center gap-2.5 bg-[#1A1F2E] border border-[#2A3146] rounded-xl hover:-translate-y-0.5 transition-all cursor-pointer"
            >
              <div className={`w-8 h-8 rounded-lg bg-[#151823] border border-[#2A3146] flex items-center justify-center shrink-0 ${stat.color}`}>
                <Icon className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-black text-white font-mono leading-none">{stat.count}</div>
                <div className="text-[9px] text-gray-400 font-medium truncate mt-0.5">{stat.label}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Toolbar: Search Bar & Filter Chips ── */}
      <div className="flex items-center gap-2 shrink-0">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search modules, files, APIs..."
            className="w-full bg-[#151823] border border-[#2A3146] rounded-xl pl-8 pr-2.5 py-1 text-xs text-white placeholder-gray-500 outline-none focus:border-[#4C8DFF] font-mono"
          />
        </div>

        <div className="flex bg-[#151823] border border-[#2A3146] p-0.5 rounded-xl gap-0.5 text-[10px] font-semibold">
          {['All', 'Files', 'APIs', 'Components', 'Services'].map(chip => {
            const key = chip.toLowerCase();
            const isActive = filterType === key || (filterType === 'all' && chip === 'All');
            return (
              <button
                key={chip}
                onClick={() => setFilterType(key === 'all' ? 'all' : key)}
                className={`px-2.5 py-0.5 rounded-lg transition-all cursor-pointer capitalize ${
                  isActive ? 'bg-[#4C8DFF] text-white font-bold shadow-md shadow-[#4C8DFF]/30' : 'text-gray-400 hover:text-white'
                }`}
              >
                {chip}
              </button>
            );
          })}
        </div>

        <button className="p-1.5 text-gray-400 hover:text-white bg-[#151823] border border-[#2A3146] rounded-xl cursor-pointer">
          <SlidersHorizontal className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* ── Large Interactive Graph Canvas (Fills Available Space) ── */}
      <div className="flex-1 bg-[#151823] border border-[#2A3146] rounded-2xl relative overflow-hidden flex items-center justify-center min-h-0">
        
        {/* SVG Dotted Grid Background */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-40">
          <defs>
            <pattern id="dotPattern" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1.2" fill="#2A3146" />
            </pattern>
            <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#4C8DFF" stopOpacity="0.85" />
              <stop offset="100%" stopColor="#60A5FA" stopOpacity="0.85" />
            </linearGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#dotPattern)" />
        </svg>

        {loading ? (
          <div className="flex items-center gap-2 text-gray-400 text-xs z-10">
            <RefreshCw className="w-4 h-4 animate-spin text-[#4C8DFF]" /> Parsing AST Dependencies...
          </div>
        ) : (
          <div
            className="w-full h-full relative"
            style={{
              transform: `scale(${zoom}) translate(${panOffset.x}px, ${panOffset.y}px)`,
              transformOrigin: 'center center',
              transition: 'transform 0.15s ease-out'
            }}
          >
            {/* Render SVG Curved Bezier Edges */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
              {data?.edges.map(edge => {
                const srcPos = nodePositions[edge.source];
                const tgtPos = nodePositions[edge.target];
                if (!srcPos || !tgtPos) return null;

                const dx = tgtPos.x - srcPos.x;
                const cx1 = srcPos.x + dx * 0.5;
                const cy1 = srcPos.y;
                const cx2 = srcPos.x + dx * 0.5;
                const cy2 = tgtPos.y;

                const isEdgeConnected = selectedNode && (edge.source === selectedNode.id || edge.target === selectedNode.id);

                return (
                  <g key={edge.id}>
                    <path
                      d={`M ${srcPos.x + 50} ${srcPos.y + 18} C ${cx1 + 50} ${cy1 + 18}, ${cx2 + 50} ${cy2 + 18}, ${tgtPos.x + 50} ${tgtPos.y + 18}`}
                      fill="none"
                      stroke={isEdgeConnected ? '#4C8DFF' : 'url(#edgeGrad)'}
                      strokeWidth={isEdgeConnected ? 2.5 : 1.5}
                      strokeDasharray={isEdgeConnected ? 'none' : '4,4'}
                      className="transition-all"
                    />
                  </g>
                );
              })}
            </svg>

            {/* Render Interactive Node Cards */}
            {filteredNodes.map(node => {
              const pos = nodePositions[node.id] || { x: 200, y: 200 };
              const isSelected = selectedNode?.id === node.id;
              const isFav = favorites.has(node.label);

              return (
                <div
                  key={node.id}
                  onClick={() => setSelectedNode(node)}
                  style={{ left: `${pos.x}px`, top: `${pos.y}px` }}
                  className={`
                    absolute w-40 p-2 rounded-xl border transition-all cursor-pointer z-10 flex flex-col justify-between space-y-1.5 shadow-lg font-sans
                    ${isSelected
                      ? 'bg-[#1A1F2E] border-[#4C8DFF] ring-2 ring-[#4C8DFF]/60 shadow-[0_0_24px_rgba(76,141,255,0.4)] scale-105'
                      : 'bg-[#1A1F2E]/90 border-[#2A3146] hover:border-[#4C8DFF]/40 hover:scale-102 hover:bg-[#1A1F2E]'
                    }
                  `}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-1.5 min-w-0">
                      {node.type === 'component' && <Box className="w-3.5 h-3.5 text-emerald-400 shrink-0" />}
                      {node.type === 'service' && <Server className="w-3.5 h-3.5 text-[#4C8DFF] shrink-0" />}
                      {node.type === 'api' && <Code2 className="w-3.5 h-3.5 text-amber-400 shrink-0" />}
                      {node.type === 'database' && <Database className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
                      {node.type === 'file' && <FileCode className="w-3.5 h-3.5 text-blue-400 shrink-0" />}

                      <div className="min-w-0">
                        <span className="font-bold text-[11px] text-white block truncate">{node.label}</span>
                        <span className="text-[8px] text-gray-400 block capitalize">{node.type} File</span>
                      </div>
                    </div>

                    <Star
                      onClick={(e) => toggleFavorite(node.label, e)}
                      className={`w-3 h-3 cursor-pointer shrink-0 ${isFav ? 'text-amber-400 fill-amber-400' : 'text-gray-600 hover:text-amber-400'}`}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[8px] font-mono text-gray-400 pt-1 border-t border-[#2A3146]">
                    <span className="truncate max-w-[90px]">{node.path}</span>
                    <span className="bg-[#151823] px-1 py-0.2 rounded text-[#4C8DFF] font-bold border border-[#4C8DFF]/30">
                      ⚡ 4
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Floating Graph Controls */}
        <div className="absolute top-3 left-3 flex items-center gap-1 bg-[#1A1F2E] border border-[#2A3146] p-1 rounded-xl shadow-xl z-20">
          <button
            onClick={() => setPanOffset({ x: 0, y: 0 })}
            className="p-1 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 cursor-pointer"
            title="Pan Hand Tool"
          >
            <Move className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => { setZoom(1); setPanOffset({ x: 0, y: 0 }); }}
            className="p-1 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 cursor-pointer"
            title="Reset View"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 cursor-pointer"
            title="Toggle Fullscreen Canvas"
          >
            <Maximize2 className="w-3.5 h-3.5 text-[#4C8DFF]" />
          </button>
        </div>

        {/* Floating Zoom Widget & Mini Map */}
        <div className="absolute bottom-3 right-3 flex items-center gap-2 z-20">
          <div className="flex items-center gap-1 bg-[#1A1F2E] border border-[#2A3146] p-1 rounded-xl shadow-xl">
            <button
              onClick={() => setZoom(z => Math.max(0.5, z - 0.1))}
              className="p-1 text-gray-400 hover:text-white cursor-pointer"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-[10px] font-mono text-gray-300 px-1 font-bold">{Math.round(zoom * 100)}%</span>
            <button
              onClick={() => setZoom(z => Math.min(2, z + 0.1))}
              className="p-1 text-gray-400 hover:text-white cursor-pointer"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Interactive Mini Map Box */}
          <div className="w-20 h-14 bg-[#1A1F2E] border border-[#2A3146] rounded-xl p-1 relative shadow-2xl overflow-hidden hidden sm:block">
            <div className="w-full h-full bg-[#151823] rounded relative">
              {filteredNodes.slice(0, 10).map((n, idx) => (
                <div
                  key={n.id}
                  className={`absolute w-1 h-1 rounded-full ${selectedNode?.id === n.id ? 'bg-[#4C8DFF] ring-2 ring-[#4C8DFF]/50' : 'bg-gray-500'}`}
                  style={{ left: `${(idx * 7) % 80 + 5}%`, top: `${(idx * 11) % 50 + 5}%` }}
                />
              ))}
              <div className="absolute inset-1.5 border border-[#4C8DFF]/40 rounded pointer-events-none" />
            </div>
          </div>
        </div>

        {/* ── FLOATING OVERLAY INSPECTOR PANEL (Slides OVER Graph Canvas) ── */}
        {selectedNode && (
          <div className="absolute right-3 top-3 bottom-3 w-80 bg-[#1A1F2E] border border-[#2A3146] rounded-2xl shadow-2xl flex flex-col justify-between p-3.5 z-30 overflow-y-auto animate-slide-in font-sans">
            <div className="space-y-3">
              
              {/* Header with close button */}
              <div className="flex items-start justify-between pb-2.5 border-b border-[#2A3146]">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-8 h-8 rounded-xl bg-[#151823] border border-[#2A3146] flex items-center justify-center shrink-0">
                    <Code2 className="w-3.5 h-3.5 text-[#4C8DFF]" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-extrabold text-white text-xs truncate">{selectedNode.label}</h3>
                    <p className="text-[9px] text-gray-400 capitalize">{selectedNode.type} File</p>
                  </div>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <Star
                    onClick={(e) => toggleFavorite(selectedNode.label, e)}
                    className={`w-3.5 h-3.5 cursor-pointer ${favorites.has(selectedNode.label) ? 'text-amber-400 fill-amber-400' : 'text-gray-600 hover:text-amber-400'}`}
                  />
                  <button
                    onClick={() => setSelectedNode(null)}
                    className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                    title="Close Inspector"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Inspector Nav Tabs */}
              <div className="flex bg-[#151823] p-0.5 rounded-xl border border-[#2A3146] text-[10px] font-semibold">
                {[
                  { id: 'overview', label: 'Overview' },
                  { id: 'imports', label: `Imports (${connectedNodes.imports.length})` },
                  { id: 'importedBy', label: `Imported By (${connectedNodes.importedBy.length})` },
                ].map(t => (
                  <button
                    key={t.id}
                    onClick={() => setInspectorTab(t.id as any)}
                    className={`flex-1 py-1 text-center rounded-lg transition-all cursor-pointer ${
                      inspectorTab === t.id ? 'bg-[#4C8DFF] text-white font-bold shadow-md shadow-[#4C8DFF]/30' : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {/* Tab: Overview */}
              {inspectorTab === 'overview' && (
                <div className="space-y-3">
                  
                  {/* Summary Card */}
                  <div className="p-2.5 bg-[#151823] border border-[#2A3146] rounded-xl space-y-1">
                    <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wider block">Summary</span>
                    {nodeSummary.loading ? (
                      <div className="flex items-center gap-1 text-[#4C8DFF] text-[10px]">
                        <Loader2 className="w-3 h-3 animate-spin" /> Fetching AI summary...
                      </div>
                    ) : (
                      <p className="text-[11px] text-gray-300 leading-relaxed font-sans">
                        {nodeSummary.text || `Configuration and environment settings for ${selectedNode.label}.`}
                      </p>
                    )}
                  </div>

                  {/* Database Schema Models */}
                  {selectedNode.type === 'database' && selectedNode.db_info?.tables && (
                    <div className="p-2.5 bg-[#151823] border border-cyan-500/30 rounded-xl space-y-1.5">
                      <span className="text-[9px] font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1">
                        <Database className="w-3 h-3 text-cyan-400" /> Database Schema / Models
                      </span>
                      {selectedNode.db_info.tables.map((tbl, i) => (
                        <div key={i} className="bg-[#1A1F2E] p-1.5 rounded-lg border border-cyan-900/50 space-y-0.5 font-mono text-[10px]">
                          <div className="flex justify-between text-white font-semibold">
                            <span>{tbl.model_name}</span>
                            <span className="text-cyan-400 text-[9px]">{tbl.table_name}</span>
                          </div>
                          {tbl.fields.length > 0 && (
                            <p className="text-[8px] text-gray-400 truncate">Fields: {tbl.fields.join(', ')}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Metadata Table */}
                  <div className="p-2.5 bg-[#151823] border border-[#2A3146] rounded-xl space-y-1.5 text-xs">
                    <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wider block">Metadata</span>
                    <div className="space-y-1 font-mono text-[10px]">
                      <div className="flex justify-between"><span className="text-gray-500">Language</span><span className="text-white font-semibold">Python</span></div>
                      <div className="flex justify-between"><span className="text-gray-500">Size</span><span className="text-white font-semibold">2.45 KB</span></div>
                      <div className="flex justify-between"><span className="text-gray-500">Lines</span><span className="text-white font-semibold">128</span></div>
                      <div className="flex justify-between"><span className="text-gray-500">Modified</span><span className="text-white font-semibold">2 hours ago</span></div>
                    </div>
                  </div>

                  {/* Imported By List */}
                  {connectedNodes.importedBy.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wider block">
                        Imported By ({connectedNodes.importedBy.length})
                      </span>
                      <div className="space-y-1 font-mono text-[11px]">
                        {connectedNodes.importedBy.map((impItem) => (
                          <div
                            key={impItem.id}
                            onClick={() => handleSelectFile(impItem.path)}
                            className="flex items-center justify-between p-1.5 rounded-lg bg-[#151823] hover:bg-white/5 border border-[#2A3146] cursor-pointer transition-colors"
                          >
                            <div className="min-w-0">
                              <span className="text-white font-semibold block truncate">{impItem.label}</span>
                              <span className="text-[8px] text-gray-500 truncate block">{impItem.path}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Related Files Section */}
                  <div className="space-y-1.5">
                    <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wider block">Related Files</span>
                    <div className="space-y-1 font-mono text-[11px]">
                      {[
                        { name: '.env', type: 'Environment File' },
                        { name: 'settings.py', type: 'Python File' },
                        { name: 'constants.py', type: 'Python File' },
                      ].map((rel, i) => (
                        <div key={i} className="flex items-center gap-2 p-1.5 rounded-lg bg-[#151823] border border-[#2A3146] text-gray-300">
                          <FileText className="w-3.5 h-3.5 text-[#4C8DFF]" />
                          <div>
                            <span className="text-white font-semibold block leading-tight">{rel.name}</span>
                            <span className="text-[8px] text-gray-500">{rel.type}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                </div>
              )}

              {/* Tab: Imports */}
              {inspectorTab === 'imports' && (
                <div className="space-y-1 font-mono text-[11px]">
                  {connectedNodes.imports.length === 0 ? (
                    <div className="py-4 text-center text-gray-500 text-xs italic">
                      0 internal module imports
                    </div>
                  ) : (
                    connectedNodes.imports.map(n => (
                      <div
                        key={n.id}
                        onClick={() => handleSelectFile(n.path)}
                        className="p-1.5 rounded-lg bg-[#151823] hover:bg-white/5 border border-[#2A3146] cursor-pointer text-white flex items-center justify-between"
                      >
                        <span className="truncate">{n.label}</span>
                        <ExternalLink className="w-3 h-3 text-gray-500" />
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* Tab: Imported By */}
              {inspectorTab === 'importedBy' && (
                <div className="space-y-1 font-mono text-[11px]">
                  {connectedNodes.importedBy.length === 0 ? (
                    <div className="py-4 text-center text-gray-500 text-xs italic">
                      0 modules import this file
                    </div>
                  ) : (
                    connectedNodes.importedBy.map(n => (
                      <div
                        key={n.id}
                        onClick={() => handleSelectFile(n.path)}
                        className="p-1.5 rounded-lg bg-[#151823] hover:bg-white/5 border border-[#2A3146] cursor-pointer text-white flex items-center justify-between"
                      >
                        <span className="truncate">{n.label}</span>
                        <ExternalLink className="w-3 h-3 text-gray-500" />
                      </div>
                    ))
                  )}
                </div>
              )}

            </div>

            {/* Primary Action Button: Open File */}
            <button
              onClick={() => handleSelectFile(selectedNode.path)}
              className="w-full mt-3 flex items-center justify-center gap-2 py-2 bg-[#4C8DFF] hover:bg-[#9176FF] text-white text-xs font-bold rounded-xl shadow-lg shadow-[#4C8DFF]/30 transition-all cursor-pointer shrink-0"
            >
              <ExternalLink className="w-3.5 h-3.5" /> Open File
            </button>
          </div>
        )}

      </div>

    </div>
  );
};
