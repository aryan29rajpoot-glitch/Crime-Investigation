"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";
import { getLayoutedElements } from "./graphLayout";

// ============================================================
// TYPES
// ============================================================

type EntityRisk = {
  id: string;
  score: number;
  level: string;
  role: string;
  reasons: string[];
};

type GraphNodeData = {
  id: string;
  type: string;
  role?: string;
  total_inflow?: number;
  total_outflow?: number;
  call_count?: number;
  chat_mentions?: number;
  first_seen?: string | null;
  last_seen?: string | null;
  degree_centrality?: number;
  betweenness?: number;
  risk?: EntityRisk;
  isSelected?: boolean;
};

type GraphEdgeData = {
  source: string;
  target: string;
  relationship: string;
  amount: number | null;
  timestamp: string | null;
  duration?: number | null;
  snippet?: string | null;
  channel?: string;
};

type TimelineEvent = {
  timestamp: string | null;
  type: string;
  channel: string;
  source: string;
  target: string | null;
  amount?: number | null;
  description: string;
};

type CaseItem = {
  case_id: string;
  title: string;
  description: string;
  created_at: string;
  is_default?: boolean;
  has_cdr?: boolean;
  has_bank?: boolean;
  has_chat?: boolean;
};

type Analysis = {
  case_id: string;
  metadata: {
    title: string;
    description: string;
    created_at: string;
    is_default: boolean;
  };
  evidence: {
    cdr_records: number;
    bank_records: number;
    chat_evidence: boolean;
    chat_messages: number;
    rapid_transfer_flag: boolean;
    cross_channel_nexus: boolean;
  };
  entities: {
    phones: string[];
    upi_ids: string[];
    bank_accounts: string[];
    ip_addresses: string[];
  };
  graph: {
    nodes: number;
    relationships: number;
    node_data: GraphNodeData[];
    edge_data: GraphEdgeData[];
    metrics: {
      node_count: number;
      edge_count: number;
      mule_nodes: string[];
      suspect_nodes: string[];
      victim_nodes: string[];
      density: number;
    };
  };
  risk_analysis: {
    score: number;
    level: string;
    reasons: string[];
    entity_risks: Record<string, EntityRisk>;
  };
  timeline: TimelineEvent[];
};

const API_BASE = "http://127.0.0.1:8000";

// ============================================================
// CUSTOM NODE COMPONENT
// ============================================================

function EntityNode({ data }: NodeProps) {
  const nodeData = data as unknown as GraphNodeData;
  const type = nodeData.type;
  const role = nodeData.role || "UNKNOWN";

  let icon = "☎";
  let typeLabel = "PHONE";

  if (type === "bank_account") {
    icon = "₹";
    typeLabel = "BANK ACCOUNT";
  } else if (type === "upi") {
    icon = "@";
    typeLabel = "UPI ID";
  } else if (type === "ip") {
    icon = "◉";
    typeLabel = "IP ADDRESS";
  }

  let roleClass = "role-default";
  let roleLabel = role.replace("_", " ");
  if (role === "MULE_ACCOUNT") {
    roleClass = "role-mule";
    roleLabel = "MULE ACC";
  } else if (role.includes("SUSPECT")) {
    roleClass = "role-suspect";
    roleLabel = "SUSPECT";
  } else if (role === "VICTIM_ACCOUNT") {
    roleClass = "role-victim";
    roleLabel = "VICTIM";
  } else if (role === "CASHOUT_NODE") {
    roleClass = "role-cashout";
    roleLabel = "CASHOUT";
  }

  const isSelected = Boolean(nodeData.isSelected);

  return (
    <div className={`entity-node entity-${type} ${isSelected ? "selected" : ""}`}>
      {role !== "UNKNOWN" && (
        <span className={`node-role-badge ${roleClass}`}>{roleLabel}</span>
      )}

      <Handle type="target" position={Position.Left} className="custom-handle" />

      <div className="entity-icon">{icon}</div>

      <div className="entity-content">
        <div className="entity-id" title={nodeData.id}>
          {nodeData.id}
        </div>
        <div className="entity-type">{typeLabel}</div>
      </div>

      <Handle type="source" position={Position.Right} className="custom-handle" />
    </div>
  );
}

const nodeTypes = {
  entity: EntityNode,
};

function relationshipColor(relationship: string) {
  switch (relationship) {
    case "CALL":
      return "#5ca9ff";
    case "CHAT_LINK":
      return "#45d6a3";
    case "DEBIT":
    case "CREDIT":
    case "TRANSFER":
      return "#e5a93d";
    default:
      return "#8792a8";
  }
}

function relationshipWidth(relationship: string) {
  switch (relationship) {
    case "TRANSFER":
      return 4;
    case "DEBIT":
    case "CREDIT":
      return 3;
    default:
      return 2;
  }
}

// ============================================================
// MAIN PAGE
// ============================================================

export default function Home() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string>("CYBER-2026-001");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Interactive filtering & inspection state
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeData, setSelectedEdgeData] = useState<GraphEdgeData | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<string>("ALL");
  const [activeTimelineIndex, setActiveTimelineIndex] = useState<number | null>(null);

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadCaseId, setUploadCaseId] = useState("");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadDesc, setUploadDesc] = useState("");
  const [cdrFile, setCdrFile] = useState<File | null>(null);
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [chatFile, setChatFile] = useState<File | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const cdrInputRef = useRef<HTMLInputElement>(null);
  const bankInputRef = useRef<HTMLInputElement>(null);
  const chatInputRef = useRef<HTMLInputElement>(null);

  // Fetch data inside useEffect cleanly without synchronous setState calls
  useEffect(() => {
    let isCancelled = false;

    async function initData() {
      try {
        const [casesRes, analysisRes] = await Promise.all([
          fetch(`${API_BASE}/cases`).catch(() => null),
          fetch(
            activeCaseId === "CYBER-2026-001"
              ? `${API_BASE}/analyze`
              : `${API_BASE}/cases/${encodeURIComponent(activeCaseId)}/analyze`
          ).catch(() => null),
        ]);

        if (isCancelled) return;

        if (casesRes && casesRes.ok) {
          const casesData = await casesRes.json();
          setCases(casesData.cases || []);
        }

        if (analysisRes && analysisRes.ok) {
          const data = await analysisRes.json();
          setAnalysis(data);
          setError("");
        } else if (analysisRes) {
          setError(`Failed to load case analysis (HTTP ${analysisRes.status})`);
        } else {
          setError("Unable to connect to FraudLens backend engine. Ensure FastAPI is running on port 8000.");
        }
      } catch (err) {
        if (!isCancelled) {
          console.error(err);
          setError("Unable to connect to FraudLens backend engine.");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    initData();

    return () => {
      isCancelled = true;
    };
  }, [activeCaseId]);

  // Handle case change
  const handleCaseChange = (caseId: string) => {
    setLoading(true);
    setSelectedNodeId(null);
    setSelectedEdgeData(null);
    setActiveCaseId(caseId);
  };

  const fetchCases = async () => {
    try {
      const res = await fetch(`${API_BASE}/cases`);
      if (res.ok) {
        const data = await res.json();
        setCases(data.cases || []);
      }
    } catch (err) {
      console.error("Failed to load cases:", err);
    }
  };

  const reloadActiveCase = () => {
    setLoading(true);
    setSelectedNodeId(null);
    setSelectedEdgeData(null);
    // Trigger re-fetch by keeping activeCaseId
    fetch(
      activeCaseId === "CYBER-2026-001"
        ? `${API_BASE}/analyze`
        : `${API_BASE}/cases/${encodeURIComponent(activeCaseId)}/analyze`
    )
      .then((res) => res.json())
      .then((data) => {
        setAnalysis(data);
        setError("");
      })
      .catch((err) => {
        console.error(err);
        setError("Failed to refresh case analysis.");
      })
      .finally(() => setLoading(false));
  };

  // Handle case upload submission
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadCaseId.trim()) {
      setUploadError("Please provide a Case ID.");
      return;
    }
    if (!cdrFile && !bankFile && !chatFile) {
      setUploadError("Please upload at least one evidence file (CDR, Bank, or Chat).");
      return;
    }

    try {
      setUploadLoading(true);
      setUploadError("");

      const formData = new FormData();
      formData.append("case_id", uploadCaseId.trim());
      formData.append("title", uploadTitle.trim());
      formData.append("description", uploadDesc.trim());
      if (cdrFile) formData.append("cdr_file", cdrFile);
      if (bankFile) formData.append("bank_file", bankFile);
      if (chatFile) formData.append("chat_file", chatFile);

      const res = await fetch(`${API_BASE}/cases/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Upload failed");
      }

      const resData = await res.json();
      await fetchCases();
      setIsUploadOpen(false);
      setUploadCaseId("");
      setUploadTitle("");
      setUploadDesc("");
      setCdrFile(null);
      setBankFile(null);
      setChatFile(null);

      // Switch to new case
      const newId = resData.case?.case_id || uploadCaseId.trim().toUpperCase();
      setActiveCaseId(newId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to upload case";
      setUploadError(msg);
    } finally {
      setUploadLoading(false);
    }
  };

  // Export Case Dossier as JSON
  const handleExportDossier = () => {
    if (!analysis) return;
    const exportData = {
      dossier_type: "FRAUDLENS_CYBER_INCIDENT_REPORT",
      case_id: analysis.case_id,
      generated_at: new Date().toISOString(),
      metadata: analysis.metadata,
      threat_level: analysis.risk_analysis.level,
      overall_risk_score: analysis.risk_analysis.score,
      detection_reasons: analysis.risk_analysis.reasons,
      summary_metrics: {
        total_entities: analysis.graph.nodes,
        total_connections: analysis.graph.relationships,
        identified_mules: analysis.graph.metrics.mule_nodes,
        identified_suspects: analysis.graph.metrics.suspect_nodes,
        identified_victims: analysis.graph.metrics.victim_nodes,
      },
      entity_registry: analysis.graph.node_data,
      chronological_timeline: analysis.timeline,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `FraudLens_${analysis.case_id}_Dossier.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Selected Entity Details
  const selectedEntity = useMemo(() => {
    if (!analysis || !selectedNodeId) return null;
    const node = analysis.graph.node_data.find((n) => n.id === selectedNodeId);
    if (!node) return null;

    // Find all directly connected edges
    const directEdges = analysis.graph.edge_data.filter(
      (e) => e.source === selectedNodeId || e.target === selectedNodeId
    );

    return {
      ...node,
      directEdges,
    };
  }, [analysis, selectedNodeId]);

  // Build Layouted Graph Nodes & Edges
  const { nodes, edges } = useMemo<{ nodes: Node[]; edges: Edge[] }>(() => {
    if (!analysis) return { nodes: [], edges: [] };

    let graphNodes = analysis.graph.node_data;
    let graphEdges = analysis.graph.edge_data;

    // Filter by Search Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchingNodeIds = new Set(
        graphNodes.filter((n) => n.id.toLowerCase().includes(q)).map((n) => n.id)
      );
      // Keep matching nodes and edges attached to them
      graphEdges = graphEdges.filter(
        (e) => matchingNodeIds.has(e.source) || matchingNodeIds.has(e.target)
      );
    }

    // Filter by Active Filter Chip
    if (activeFilter === "FINANCIAL") {
      graphEdges = graphEdges.filter((e) =>
        ["DEBIT", "CREDIT", "TRANSFER"].includes(e.relationship)
      );
    } else if (activeFilter === "CALLS") {
      graphEdges = graphEdges.filter((e) => e.relationship === "CALL");
    } else if (activeFilter === "CHATS") {
      graphEdges = graphEdges.filter((e) => e.relationship === "CHAT_LINK");
    } else if (activeFilter === "MULES") {
      const muleSet = new Set(analysis.graph.metrics.mule_nodes);
      graphNodes = graphNodes.filter((n) => muleSet.has(n.id));
      graphEdges = graphEdges.filter(
        (e) => muleSet.has(e.source) || muleSet.has(e.target)
      );
    } else if (activeFilter === "HIGH_RISK") {
      graphNodes = graphNodes.filter((n) => (n.risk?.score || 0) >= 60);
      const highSet = new Set(graphNodes.map((n) => n.id));
      graphEdges = graphEdges.filter(
        (e) => highSet.has(e.source) || highSet.has(e.target)
      );
    }

    // Convert to XYFlow nodes
    const rawFlowNodes: Node[] = graphNodes.map((node) => ({
      id: node.id,
      type: "entity",
      position: { x: 0, y: 0 },
      data: {
        ...node,
        isSelected: selectedNodeId === node.id,
      },
    }));

    // Convert to XYFlow edges
    const rawFlowEdges: Edge[] = graphEdges.map((edge, index) => {
      const color = relationshipColor(edge.relationship);
      let label = edge.relationship;
      if (edge.amount !== null && edge.amount !== undefined) {
        label = `${edge.relationship} ₹${edge.amount.toLocaleString("en-IN")}`;
      }

      const isConnectedToSelected =
        selectedNodeId &&
        (edge.source === selectedNodeId || edge.target === selectedNodeId);

      return {
        id: `edge-${index}-${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated:
          edge.relationship === "TRANSFER" ||
          edge.relationship === "DEBIT" ||
          edge.relationship === "CREDIT",
        label,
        data: edge,
        style: {
          stroke: isConnectedToSelected ? "#ffa834" : color,
          strokeWidth: isConnectedToSelected ? 4 : relationshipWidth(edge.relationship),
        },
        labelStyle: {
          fill: isConnectedToSelected ? "#ffa834" : "#e8edf7",
          fontSize: 11,
          fontWeight: 700,
        },
        labelBgStyle: {
          fill: "#07101d",
          fillOpacity: 0.95,
          stroke: isConnectedToSelected ? "#ffa834" : color,
          strokeWidth: 1,
        },
        labelBgPadding: [6, 4],
        markerEnd: {
          type: "arrowclosed",
          color: isConnectedToSelected ? "#ffa834" : color,
        },
      };
    });

    // Auto-layout with Dagre
    return getLayoutedElements(rawFlowNodes, rawFlowEdges, "LR");
  }, [analysis, searchQuery, activeFilter, selectedNodeId]);

  if (loading) {
    return (
      <main className="loading-screen">
        <div className="loading-box">
          <div className="loading-spinner" />
          <h2>FraudLens Forensics Engine</h2>
          <p>Correlating telecommunications, financial records, and chat transcripts...</p>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="error-screen">
        <div className="error-box">
          <div className="error-icon">!</div>
          <h1>Investigation Engine Connection Failed</h1>
          <p>{error}</p>
          <button onClick={reloadActiveCase}>↻ Retry Connection</button>
        </div>
      </main>
    );
  }

  if (!analysis) return null;

  const risk = analysis.risk_analysis.score;

  return (
    <main className="app">
      {/* HEADER */}
      <header className="header">
        <div className="brand">
          <div className="brand-mark">FL</div>
          <div>
            <div className="brand-name">FRAUDLENS</div>
            <div className="brand-subtitle">CROSS-CHANNEL ARTIFACT CORRELATION</div>
          </div>
        </div>

        <div className="header-actions">
          {/* Case Switcher Dropdown */}
          <div className="active-case">
            <span>ACTIVE INVESTIGATION</span>
            <select
              className="case-select"
              value={activeCaseId}
              onChange={(e) => handleCaseChange(e.target.value)}
            >
              {cases.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.case_id} - {c.title}
                </option>
              ))}
            </select>
          </div>

          <button className="btn-primary" onClick={() => setIsUploadOpen(true)}>
            + New Case Upload
          </button>

          <button className="btn-secondary" onClick={handleExportDossier}>
            ↓ Export Dossier
          </button>

          <button className="refresh-button" onClick={reloadActiveCase} title="Refresh Case">
            ↻
          </button>
        </div>
      </header>

      {/* PAGE TITLE & STATUS */}
      <section className="page-heading">
        <div>
          <div className="eyebrow">CASE DOSSIER / {analysis.case_id}</div>
          <h1>{analysis.metadata.title || "Digital Evidence Analysis"}</h1>
          <p style={{ color: "#6e829d", fontSize: "13px", marginTop: "4px" }}>
            {analysis.metadata.description || "Correlated cyber crime artifacts and money flow tracking"}
          </p>
        </div>

        <div className="analysis-status">
          <span className="status-dot" />
          {analysis.evidence.rapid_transfer_flag ? "HIGH VELOCITY ALERT" : "ANALYSIS ACTIVE"}
        </div>
      </section>

      {/* STAT CARDS */}
      <section className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">CDR RECORDS</div>
          <div className="stat-value">{analysis.evidence.cdr_records}</div>
          <div className="stat-description">Telecom call logs</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">BANK TRANSFERS</div>
          <div className="stat-value">{analysis.evidence.bank_records}</div>
          <div className="stat-description">Financial transactions</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">TOTAL ENTITIES</div>
          <div className="stat-value">{analysis.graph.nodes}</div>
          <div className="stat-description">Unique forensic nodes</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">DETECTED MULES</div>
          <div className="stat-value" style={{ color: "#ffaa42" }}>
            {analysis.graph.metrics.mule_nodes.length}
          </div>
          <div className="stat-description">Pass-through accounts</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">CROSS-CHANNEL NEXUS</div>
          <div
            className="stat-value chat-value"
            style={{ color: analysis.evidence.cross_channel_nexus ? "#ff5466" : "#45d6a3" }}
          >
            {analysis.evidence.cross_channel_nexus ? "CONFIRMED" : "PARTIAL"}
          </div>
          <div className="stat-description">Call + Chat + UPI Nexus</div>
        </div>
      </section>

      {/* MAIN CONTENT: GRAPH + RISK */}
      <section className="main-grid">
        {/* GRAPH PANEL */}
        <div className="graph-panel">
          <div className="panel-header">
            <div>
              <div className="panel-eyebrow">GRAPH INTELLIGENCE</div>
              <h2>Unified Artifact Relationship Graph</h2>
            </div>
            <div className="node-count">{analysis.graph.nodes} NODES / {analysis.graph.relationships} RELATIONS</div>
          </div>

          {/* SEARCH & FILTER BAR */}
          <div className="search-filter-bar">
            <div className="search-input-wrapper">
              <span>🔍</span>
              <input
                type="text"
                placeholder="Search phone, UPI, bank account..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  style={{ background: "none", border: "none", color: "#667d9c", cursor: "pointer" }}
                  onClick={() => setSearchQuery("")}
                >
                  ✕
                </button>
              )}
            </div>

            <div className="filter-chips">
              <button
                className={`filter-chip ${activeFilter === "ALL" ? "active" : ""}`}
                onClick={() => setActiveFilter("ALL")}
              >
                All Artifacts
              </button>
              <button
                className={`filter-chip ${activeFilter === "MULES" ? "active" : ""}`}
                onClick={() => setActiveFilter("MULES")}
              >
                ⚠ Mule Rings ({analysis.graph.metrics.mule_nodes.length})
              </button>
              <button
                className={`filter-chip ${activeFilter === "FINANCIAL" ? "active" : ""}`}
                onClick={() => setActiveFilter("FINANCIAL")}
              >
                Financial Transfers
              </button>
              <button
                className={`filter-chip ${activeFilter === "CALLS" ? "active" : ""}`}
                onClick={() => setActiveFilter("CALLS")}
              >
                Voice Calls
              </button>
              <button
                className={`filter-chip ${activeFilter === "CHATS" ? "active" : ""}`}
                onClick={() => setActiveFilter("CHATS")}
              >
                Chat Links
              </button>
              <button
                className={`filter-chip ${activeFilter === "HIGH_RISK" ? "active" : ""}`}
                onClick={() => setActiveFilter("HIGH_RISK")}
              >
                High Risk Nodes
              </button>
            </div>
          </div>

          <div className="graph-wrapper" style={{ height: "620px" }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.2}
              maxZoom={2.0}
              nodesDraggable
              nodesConnectable={false}
              elementsSelectable
              onNodeClick={(_, node) => {
                setSelectedNodeId(node.id);
                setSelectedEdgeData(null);
              }}
              onEdgeClick={(_, edge) => {
                const edgeData = edge.data as GraphEdgeData;
                setSelectedEdgeData(edgeData);
              }}
              onPaneClick={() => {
                setSelectedNodeId(null);
                setSelectedEdgeData(null);
              }}
              proOptions={{ hideAttribution: true }}
            >
              <Background gap={32} size={1} color="#162033" />
              <Controls showInteractive={false} />
              <MiniMap
                nodeColor={(node) => {
                  const nodeData = node.data as unknown as GraphNodeData;
                  if (nodeData.role === "MULE_ACCOUNT") return "#ffaa42";
                  if (nodeData.role?.includes("SUSPECT")) return "#ff5466";
                  if (nodeData.type === "bank_account") return "#5ca9ff";
                  if (nodeData.type === "upi") return "#e5a93d";
                  return "#45d6a3";
                }}
              />
            </ReactFlow>
          </div>

          {/* GRAPH LEGEND */}
          <div className="graph-legend">
            <div className="legend-item">
              <span className="legend-line" style={{ background: "#5ca9ff" }} />
              CALL
            </div>
            <div className="legend-item">
              <span className="legend-line" style={{ background: "#e5a93d" }} />
              FINANCIAL FLOW
            </div>
            <div className="legend-item">
              <span className="legend-line" style={{ background: "#45d6a3" }} />
              CHAT EXTRACTION
            </div>
            <div className="legend-item">
              <span className="legend-line" style={{ background: "#ffaa42" }} />
              MULE INTERMEDIARY
            </div>
            <div className="legend-item">
              <span className="legend-line" style={{ background: "#ff5466" }} />
              SUSPECT IDENTITY
            </div>
          </div>
        </div>

        {/* THREAT ASSESSMENT PANEL */}
        <div className="risk-panel">
          <div className="panel-header">
            <div>
              <div className="panel-eyebrow">FORENSIC EVALUATION</div>
              <h2>Threat Assessment</h2>
            </div>
          </div>

          <div className="risk-content">
            <div className="risk-score-wrapper">
              <div
                className="risk-circle"
                style={{ "--risk": `${risk}%` } as React.CSSProperties}
              >
                <div>
                  <strong>{risk}</strong>
                  <span>/ 100</span>
                </div>
              </div>

              <div className="risk-level">
                <span>SEVERITY RATING</span>
                <strong
                  style={{
                    color:
                      risk >= 80 ? "#ff5466" : risk >= 60 ? "#ffaa42" : risk >= 35 ? "#5ca9ff" : "#22d88a",
                  }}
                >
                  {analysis.risk_analysis.level}
                </strong>
              </div>
            </div>

            <div className="risk-bar">
              <div
                className="risk-bar-fill"
                style={{
                  width: `${risk}%`,
                  background:
                    risk >= 80
                      ? "linear-gradient(90deg, #ffaa42, #ff5466)"
                      : "linear-gradient(90deg, #45d6a3, #e5a93d)",
                }}
              />
            </div>

            <div className="risk-reasons">
              <div className="reason-title">FORENSIC RISK INDICATORS</div>
              {analysis.risk_analysis.reasons.map((reason, index) => (
                <div className="reason" key={index}>
                  <span className="reason-icon">!</span>
                  <span>{reason}</span>
                </div>
              ))}
            </div>

            {/* Edge Detail View if clicked */}
            {selectedEdgeData && (
              <div className="drawer-card" style={{ marginTop: "18px", borderLeft: "3px solid #61b8ff" }}>
                <div className="panel-eyebrow" style={{ marginBottom: "6px" }}>SELECTED CONNECTION</div>
                <div style={{ fontSize: "13px", fontWeight: 700 }}>
                  {selectedEdgeData.source} ➔ {selectedEdgeData.target}
                </div>
                <div style={{ fontSize: "12px", color: "#8da2bc", marginTop: "4px" }}>
                  Relationship: <strong>{selectedEdgeData.relationship}</strong>
                </div>
                {selectedEdgeData.amount && (
                  <div style={{ fontSize: "14px", color: "#ffaa42", marginTop: "4px", fontWeight: 800 }}>
                    ₹{selectedEdgeData.amount.toLocaleString("en-IN")}
                  </div>
                )}
                {selectedEdgeData.timestamp && (
                  <div style={{ fontSize: "11px", color: "#61b8ff", marginTop: "4px" }}>
                    Timestamp: {selectedEdgeData.timestamp}
                  </div>
                )}
                {selectedEdgeData.snippet && (
                  <div style={{ fontSize: "11px", color: "#92a4bc", marginTop: "6px", fontStyle: "italic" }}>
                    &ldquo;{selectedEdgeData.snippet}&rdquo;
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* CHRONOLOGICAL TIMELINE SCRUBBER */}
      <section className="timeline-section">
        <div className="timeline-header">
          <div>
            <div className="panel-eyebrow">CHRONOLOGICAL EVENT SEQUENCE</div>
            <h2 style={{ fontSize: "16px", marginTop: "2px" }}>Forensic Incident Timeline ({analysis.timeline.length} Events)</h2>
          </div>
          <div style={{ fontSize: "11px", color: "#64748b" }}>
            Click an event to highlight participating entities in the graph
          </div>
        </div>

        <div className="timeline-scroll">
          {analysis.timeline.map((event, idx) => (
            <div
              key={idx}
              className={`timeline-card ${activeTimelineIndex === idx ? "active" : ""}`}
              onClick={() => {
                setActiveTimelineIndex(idx);
                if (event.source) setSelectedNodeId(event.source);
              }}
            >
              <div className="timeline-time">{event.timestamp || "TIME UNRECORDED"}</div>
              <span
                className="timeline-type"
                style={{
                  background:
                    event.channel === "telecom"
                      ? "#09283d"
                      : event.channel === "chat"
                      ? "#083325"
                      : "#382305",
                  color:
                    event.channel === "telecom"
                      ? "#5ca9ff"
                      : event.channel === "chat"
                      ? "#45d6a3"
                      : "#e5a93d",
                }}
              >
                {event.type}
              </span>
              <div className="timeline-desc">{event.description}</div>
            </div>
          ))}
        </div>
      </section>

      {/* EVIDENCE SUMMARY CARDS */}
      <section className="evidence-section">
        <div className="panel-eyebrow">ARTIFACT REGISTRY</div>
        <h2>Correlated Evidence Entities</h2>

        <div className="evidence-grid">
          <div className="evidence-box">
            <span>PHONE IDENTIFIERS</span>
            <strong>{analysis.entities.phones.length}</strong>
          </div>
          <div className="evidence-box">
            <span>UPI IDENTITIES</span>
            <strong>{analysis.entities.upi_ids.length}</strong>
          </div>
          <div className="evidence-box">
            <span>BANK ACCOUNTS</span>
            <strong>{analysis.entities.bank_accounts.length}</strong>
          </div>
          <div className="evidence-box">
            <span>NETWORK SINK NODES</span>
            <strong>{analysis.graph.metrics.victim_nodes.length + analysis.graph.metrics.mule_nodes.length}</strong>
          </div>
        </div>
      </section>

      {/* RELATIONSHIPS TABLE */}
      <section className="relationships-section">
        <div className="panel-eyebrow">RELATIONSHIP MATRIX</div>
        <h2>Detected Interaction Channels</h2>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>SOURCE</th>
                <th>RELATIONSHIP</th>
                <th>TARGET</th>
                <th>AMOUNT</th>
                <th>TIMESTAMP</th>
                <th>CHANNEL</th>
              </tr>
            </thead>
            <tbody>
              {analysis.graph.edge_data.map((edge, index) => (
                <tr
                  key={index}
                  style={{
                    cursor: "pointer",
                    background:
                      selectedNodeId === edge.source || selectedNodeId === edge.target
                        ? "rgba(255, 168, 52, 0.08)"
                        : "transparent",
                  }}
                  onClick={() => setSelectedEdgeData(edge)}
                >
                  <td style={{ fontWeight: 600 }}>{edge.source}</td>
                  <td>
                    <span className={`relationship-badge relationship-${edge.relationship}`}>
                      {edge.relationship}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{edge.target}</td>
                  <td style={{ color: edge.amount ? "#ffaa42" : "#718299", fontWeight: 700 }}>
                    {edge.amount !== null && edge.amount !== undefined
                      ? `₹${edge.amount.toLocaleString("en-IN")}`
                      : "—"}
                  </td>
                  <td style={{ color: "#61b8ff", fontSize: "11px" }}>{edge.timestamp || "—"}</td>
                  <td style={{ textTransform: "uppercase", fontSize: "10px", color: "#677b94" }}>
                    {edge.channel || "general"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ENTITY INSPECTOR DRAWER */}
      {selectedEntity && (
        <div className="drawer-backdrop" onClick={() => setSelectedNodeId(null)}>
          <div className="drawer" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div>
                <div className="panel-eyebrow">ENTITY DOSSIER</div>
                <h2 style={{ fontSize: "18px", marginTop: "4px" }}>{selectedEntity.id}</h2>
                <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                  <span
                    className={`node-role-badge role-${
                      selectedEntity.role === "MULE_ACCOUNT"
                        ? "mule"
                        : selectedEntity.role?.includes("SUSPECT")
                        ? "suspect"
                        : selectedEntity.role === "VICTIM_ACCOUNT"
                        ? "victim"
                        : "default"
                    }`}
                  >
                    {selectedEntity.role?.replace("_", " ")}
                  </span>
                  <span style={{ fontSize: "10px", color: "#7488a0", textTransform: "uppercase" }}>
                    {selectedEntity.type}
                  </span>
                </div>
              </div>
              <button className="drawer-close" onClick={() => setSelectedNodeId(null)}>
                ✕
              </button>
            </div>

            <div className="drawer-body">
              {/* Threat Score Card */}
              {selectedEntity.risk && (
                <div className="drawer-card">
                  <div className="panel-eyebrow">ENTITY THREAT ASSESSMENT</div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "10px" }}>
                    <div style={{ fontSize: "28px", fontWeight: 800, color: selectedEntity.risk.score >= 70 ? "#ff5466" : "#ffaa42" }}>
                      {selectedEntity.risk.score} <span style={{ fontSize: "14px", color: "#6e829d" }}>/ 100</span>
                    </div>
                    <div style={{ fontSize: "12px", fontWeight: 700, color: "#e5edf8" }}>
                      {selectedEntity.risk.level} RISK
                    </div>
                  </div>

                  <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "6px" }}>
                    {selectedEntity.risk.reasons.map((r, i) => (
                      <div key={i} style={{ fontSize: "11px", color: "#8fa3bd", display: "flex", gap: "6px" }}>
                        <span style={{ color: "#ffaa42" }}>•</span>
                        <span>{r}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Financial Metrics */}
              <div className="drawer-metric-grid">
                <div className="drawer-metric">
                  <div className="drawer-metric-label">TOTAL INFLOW</div>
                  <div className="drawer-metric-value" style={{ color: "#45d6a3" }}>
                    ₹{(selectedEntity.total_inflow || 0).toLocaleString("en-IN")}
                  </div>
                </div>
                <div className="drawer-metric">
                  <div className="drawer-metric-label">TOTAL OUTFLOW</div>
                  <div className="drawer-metric-value" style={{ color: "#ff5466" }}>
                    ₹{(selectedEntity.total_outflow || 0).toLocaleString("en-IN")}
                  </div>
                </div>
              </div>

              {/* Centrality & Communication */}
              <div className="drawer-metric-grid">
                <div className="drawer-metric">
                  <div className="drawer-metric-label">CALL INTERACTIONS</div>
                  <div className="drawer-metric-value">{selectedEntity.call_count || 0}</div>
                </div>
                <div className="drawer-metric">
                  <div className="drawer-metric-label">BETWEENNESS SCORE</div>
                  <div className="drawer-metric-value">{selectedEntity.betweenness || 0}</div>
                </div>
              </div>

              {/* Direct Connections */}
              <div>
                <div className="panel-eyebrow" style={{ marginBottom: "10px" }}>
                  DIRECT CONNECTIONS ({selectedEntity.directEdges.length})
                </div>
                <div className="connections-list">
                  {selectedEntity.directEdges.map((e, idx) => (
                    <div key={idx} className="conn-item">
                      <div>
                        <div style={{ fontWeight: 600, color: "#d9e5f5" }}>
                          {e.source === selectedEntity.id ? `➔ ${e.target}` : `⬅ ${e.source}`}
                        </div>
                        <div style={{ fontSize: "10px", color: "#61b8ff", marginTop: "2px" }}>
                          {e.relationship} {e.timestamp ? `• ${e.timestamp}` : ""}
                        </div>
                      </div>
                      {e.amount !== null && e.amount !== undefined && (
                        <div style={{ fontWeight: 700, color: "#ffaa42" }}>
                          ₹{e.amount.toLocaleString("en-IN")}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Quick Actions */}
              <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
                <button
                  className="btn-secondary"
                  style={{ flex: 1 }}
                  onClick={() => {
                    navigator.clipboard.writeText(selectedEntity.id);
                    alert(`Copied ${selectedEntity.id} to clipboard!`);
                  }}
                >
                  📋 Copy Identifier
                </button>
                <button
                  className="btn-primary"
                  style={{ flex: 1 }}
                  onClick={() => {
                    setSearchQuery(selectedEntity.id);
                    setSelectedNodeId(null);
                  }}
                >
                  🔍 Filter In Graph
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* UPLOAD EVIDENCE MODAL */}
      {isUploadOpen && (
        <div className="modal-backdrop" onClick={() => setIsUploadOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="panel-eyebrow">NEW EVIDENCE INGESTION</div>
                <h2 style={{ fontSize: "18px", marginTop: "4px" }}>Create Investigation Case</h2>
              </div>
              <button className="drawer-close" onClick={() => setIsUploadOpen(false)}>
                ✕
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="modal-body">
              {uploadError && (
                <div
                  style={{
                    background: "#2a0b12",
                    border: "1px solid #751a28",
                    color: "#ff7e88",
                    padding: "10px 14px",
                    fontSize: "12px",
                  }}
                >
                  {uploadError}
                </div>
              )}

              <div className="form-group">
                <label>CASE IDENTIFIER (REQUIRED)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. CYBER-2026-002"
                  value={uploadCaseId}
                  onChange={(e) => setUploadCaseId(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label>CASE TITLE / SUBJECT</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Telegram Task Scam & Mule Accounts"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>CASE DESCRIPTION</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Brief synopsis of reported cyber incident"
                  value={uploadDesc}
                  onChange={(e) => setUploadDesc(e.target.value)}
                />
              </div>

              {/* CDR File */}
              <div className="form-group">
                <label>CALL DETAIL RECORDS (CDR.CSV)</label>
                <input
                  type="file"
                  accept=".csv,.txt"
                  ref={cdrInputRef}
                  style={{ display: "none" }}
                  onChange={(e) => setCdrFile(e.target.files?.[0] || null)}
                />
                <div className="file-dropzone" onClick={() => cdrInputRef.current?.click()}>
                  <span style={{ fontSize: "12px", color: "#8da3be" }}>
                    {cdrFile ? cdrFile.name : "Select or drop CDR CSV file"}
                  </span>
                  <span className="file-name-label">{cdrFile ? "✓ Selected" : "Browse"}</span>
                </div>
              </div>

              {/* Bank File */}
              <div className="form-group">
                <label>BANK / UPI STATEMENTS (BANK.CSV)</label>
                <input
                  type="file"
                  accept=".csv,.txt"
                  ref={bankInputRef}
                  style={{ display: "none" }}
                  onChange={(e) => setBankFile(e.target.files?.[0] || null)}
                />
                <div className="file-dropzone" onClick={() => bankInputRef.current?.click()}>
                  <span style={{ fontSize: "12px", color: "#8da3be" }}>
                    {bankFile ? bankFile.name : "Select or drop Bank CSV file"}
                  </span>
                  <span className="file-name-label">{bankFile ? "✓ Selected" : "Browse"}</span>
                </div>
              </div>

              {/* Chat File */}
              <div className="form-group">
                <label>CHAT / MESSAGING LOGS (CHATS.TXT)</label>
                <input
                  type="file"
                  accept=".txt,.json,.csv"
                  ref={chatInputRef}
                  style={{ display: "none" }}
                  onChange={(e) => setChatFile(e.target.files?.[0] || null)}
                />
                <div className="file-dropzone" onClick={() => chatInputRef.current?.click()}>
                  <span style={{ fontSize: "12px", color: "#8da3be" }}>
                    {chatFile ? chatFile.name : "Select or drop Chat transcript text file"}
                  </span>
                  <span className="file-name-label">{chatFile ? "✓ Selected" : "Browse"}</span>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "10px" }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setIsUploadOpen(false)}
                  disabled={uploadLoading}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={uploadLoading}>
                  {uploadLoading ? "Uploading & Analyzing..." : "Upload & Run Correlation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}