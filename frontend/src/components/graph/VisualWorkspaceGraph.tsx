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

const getLanguageName = (ext?: string, label?: string): string => {
  const e = (ext || label?.split('.').pop() || '').toLowerCase().replace(/^\./, '');
  const map: Record<string, string> = {
    js: 'JavaScript', jsx: 'JavaScript (JSX)', ts: 'TypeScript', tsx: 'TypeScript (TSX)',
    py: 'Python', html: 'HTML5', css: 'CSS3', scss: 'SCSS', json: 'JSON', md: 'Markdown',
    rs: 'Rust', go: 'Go', cpp: 'C++', c: 'C', java: 'Java', rb: 'Ruby', php: 'PHP',
    sql: 'SQL', sh: 'Shell Script', yml: 'YAML', yaml: 'YAML', toml: 'TOML', txt: 'Plain Text'
  };
  return map[e] || (e ? e.toUpperCase() : 'Module');
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

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
  const [nodeStats, setNodeStats] = useState<{ size: string; lines: number; loading: boolean }>({ size: '—', lines: 0, loading: false });
  const [favorites, setFavorites] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem('loopix_graph_favorites');
      return saved ? new Set(JSON.parse(saved)) : new Set<string>();
    } catch {
      return new Set<string>();
    }
  });
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
          const defaultNode = json.nodes.find((n: GraphNode) => n.label.includes('config') || n.label.includes('main') || n.label.includes('index')) || json.nodes[0];
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

  // Fetch per-file AI summary and file stats dynamically when node is selected
  useEffect(() => {
    if (!selectedNode) {
      setNodeSummary({ loading: false, text: null });
      setNodeStats({ size: '—', lines: 0, loading: false });
      return;
    }

    let isMounted = true;
    setNodeSummary({ loading: true, text: null });
    setNodeStats({ size: '—', lines: 0, loading: true });

    // Fetch dynamic AI summary
    fetch(`/api/workspace/graph/summary/${selectedNode.id}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('session_token') || ''}` }
    })
      .then(res => res.ok ? res.json() : null)
      .then(resData => {
        if (isMounted) {
          if (resData && resData.summary) {
            setNodeSummary({ loading: false, text: resData.summary });
          } else {
            setNodeSummary({ loading: false, text: `${getLanguageName(selectedNode.extension, selectedNode.label)} module: ${selectedNode.path}` });
          }
        }
      })
      .catch(() => {
        if (isMounted) {
          setNodeSummary({ loading: false, text: `${getLanguageName(selectedNode.extension, selectedNode.label)} module: ${selectedNode.path}` });
        }
      });

    // Fetch dynamic file content & size metrics
    fetch(`/api/files/content?path=${encodeURIComponent(selectedNode.path)}`)
      .then(res => res.ok ? res.json() : null)
      .then(contentData => {
        if (isMounted && contentData) {
          const content = contentData.content || '';
          const lineCount = content ? content.split('\n').length : 0;
          const sizeStr = formatFileSize(contentData.size || content.length);
          setNodeStats({ size: sizeStr, lines: lineCount, loading: false });
        } else if (isMounted) {
          setNodeStats({ size: '—', lines: 0, loading: false });
        }
      })
      .catch(() => {
        if (isMounted) setNodeStats({ size: '—', lines: 0, loading: false });
      });

    return () => { isMounted = false; };
  }, [selectedNode]);

  const toggleFavorite = (label: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setFavorites(prev => {
      const next = new Set(prev);
      if (next.has(label)) {
        next.delete(label);
      } else {
        next.add(label);
      }
      try {
        localStorage.setItem('loopix_graph_favorites', JSON.stringify(Array.from(next)));
      } catch {}
      return next;
    });
  };

  const handleCopyMermaid = () => {
    if (!data || data.nodes.length === 0) return;
    const lines = ['graph TD'];
    data.nodes.forEach(n => {
      const cleanLabel = n.label.replace(/[^a-zA-Z0-9_.-]/g, '_');
      const cleanId = n.id.replace(/[^a-zA-Z0-9_]/g, '_');
      lines.push(`    ${cleanId}["${cleanLabel}"]`);
    });
    data.edges.forEach(e => {
      const src = e.source.replace(/[^a-zA-Z0-9_]/g, '_');
      const tgt = e.target.replace(/[^a-zA-Z0-9_]/g, '_');
      lines.push(`    ${src} --> ${tgt}`);
    });
    copyToClipboard(lines.join('\n'));
    setCopiedMermaid(true);
    setTimeout(() => setCopiedMermaid(false), 2000);
  };

  const handleExplainGraph = () => {
    if (!data) return;
    const prompt = `Analyze this codebase dependency graph:\n- Total Files: ${data.nodes.length}\n- Import Connections: ${data.edges.length}\n- Circular Imports: ${data.circular_imports.length}\nExplain the overall architecture and recommendations.`;
    handleSendMessage(prompt, 'Plan', false);
  };

  // Filter nodes based on search & filter category
  const filteredNodes = useMemo(() => {
    if (!data) return [];
    return data.nodes.filter(n => {
      const matchesSearch =
        searchQuery === '' ||
        n.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.path.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesCategory =
        filterType === 'all' ||
        n.type.toLowerCase() === filterType.toLowerCase() ||
        (filterType === 'files' && n.type === 'file');

      return matchesSearch && matchesCategory;
    });
  }, [data, searchQuery, filterType]);

  // Dynamic connected nodes calculation for the selected node
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

  // Dynamic statistics calculated directly from live data
  const statsCounts = useMemo(() => {
    if (!data) return { modules: 0, edges: 0, services: 0, apis: 0 };
    const servicesCount = data.nodes.filter(n => n.type === 'service').length;
    const apisCount = data.nodes.filter(n => n.type === 'api').length;
    return {
      modules: data.summary?.total_nodes ?? data.nodes.length,
      edges: data.summary?.total_edges ?? data.edges.length,
      services: servicesCount,
      apis: apisCount
    };
  }, [data]);

  // Dynamic related files based on workspace structure
  const relatedFiles = useMemo(() => {
    if (!selectedNode || !data) return [];
    const normalizedPath = selectedNode.path.replace(/\\/g, '/');
    const folder = normalizedPath.includes('/') ? normalizedPath.substring(0, normalizedPath.lastIndexOf('/')) : '';
    return data.nodes
      .filter(n => n.id !== selectedNode.id && (folder === '' || n.path.replace(/\\/g, '/').startsWith(folder)))
      .slice(0, 5);
  }, [selectedNode, data]);

  // Pre-calculate positions with generous node spacing for canvas
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

      {/* ── Dynamic Statistics Cards Row ── */}
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

      {/* ── Interactive Graph Canvas ── */}
      <div className="flex-1 bg-[#151823] border border-[#2A3146] rounded-2xl relative overflow-hidden flex items-center justify-center min-h-0">
        
        {loading ? (
          <div className="flex flex-col items-center justify-center text-gray-400 space-y-2">
            <Loader2 className="w-8 h-8 text-[#4C8DFF] animate-spin" />
            <span className="font-mono text-xs">Analyzing workspace structure...</span>
          </div>
        ) : filteredNodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-gray-500 space-y-2 font-mono">
            <Layers className="w-10 h-10 opacity-30" />
            <span>No modules found in active workspace</span>
          </div>
        ) : (
          <div
            className="w-full h-full relative cursor-grab active:cursor-grabbing"
            style={{
              transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoom})`,
              transformOrigin: 'center center',
              transition: 'transform 0.1s ease-out'
            }}
          >
            {/* Render SVG Connection Lines */}
            <svg className="w-full h-full absolute inset-0 pointer-events-none z-0">
              <defs>
                <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#4C8DFF" />
                </marker>
              </defs>
              {data?.edges.map((edge, idx) => {
                const srcPos = nodePositions[edge.source];
                const tgtPos = nodePositions[edge.target];
                if (!srcPos || !tgtPos) return null;

                const isEdgeConnected = selectedNode && (edge.source === selectedNode.id || edge.target === selectedNode.id);

                return (
                  <g key={idx}>
                    <line
                      x1={srcPos.x + 80}
                      y1={srcPos.y + 24}
                      x2={tgtPos.x + 80}
                      y2={tgtPos.y + 24}
                      stroke={isEdgeConnected ? '#4C8DFF' : '#2A3146'}
                      strokeWidth={isEdgeConnected ? 2.5 : 1}
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
              const connCount = (data?.edges || []).filter(e => e.source === node.id || e.target === node.id).length;

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
                        <span className="text-[8px] text-gray-400 block capitalize">{getLanguageName(node.extension, node.label)}</span>
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
                      {connCount > 0 ? `⚡ ${connCount}` : (node.extension ? `.${node.extension}` : 'file')}
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

        {/* ── FLOATING OVERLAY INSPECTOR PANEL ── */}
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
                    <p className="text-[9px] text-gray-400 capitalize">{getLanguageName(selectedNode.extension, selectedNode.label)}</p>
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
                        {nodeSummary.text || `${getLanguageName(selectedNode.extension, selectedNode.label)} module defining ${selectedNode.label}.`}
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

                  {/* Dynamic Metadata Table */}
                  <div className="p-2.5 bg-[#151823] border border-[#2A3146] rounded-xl space-y-1.5 text-xs">
                    <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wider block">Metadata</span>
                    <div className="space-y-1 font-mono text-[10px]">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Language</span>
                        <span className="text-white font-semibold">{getLanguageName(selectedNode.extension, selectedNode.label)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Path</span>
                        <span className="text-white font-semibold truncate max-w-[170px]" title={selectedNode.path}>{selectedNode.path}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Size</span>
                        <span className="text-white font-semibold">
                          {nodeStats.loading ? '...' : nodeStats.size}
                        </span>
                      </div>
                      {nodeStats.lines > 0 && (
                        <div className="flex justify-between">
                          <span className="text-gray-500">Lines</span>
                          <span className="text-white font-semibold">{nodeStats.lines}</span>
                        </div>
                      )}
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

                  {/* Dynamic Related Files in Directory */}
                  {relatedFiles.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wider block">
                        Workspace Files ({relatedFiles.length})
                      </span>
                      <div className="space-y-1 font-mono text-[11px]">
                        {relatedFiles.map((rel) => (
                          <div
                            key={rel.id}
                            onClick={() => handleSelectFile(rel.path)}
                            className="flex items-center gap-2 p-1.5 rounded-lg bg-[#151823] hover:bg-white/5 border border-[#2A3146] text-gray-300 cursor-pointer transition-colors"
                          >
                            <FileText className="w-3.5 h-3.5 text-[#4C8DFF]" />
                            <div className="min-w-0 flex-1">
                              <span className="text-white font-semibold block leading-tight truncate">{rel.label}</span>
                              <span className="text-[8px] text-gray-500 capitalize">{getLanguageName(rel.extension, rel.label)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

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
