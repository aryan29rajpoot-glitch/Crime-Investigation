"use client";

import { useEffect, useMemo, useState } from "react";
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

type GraphNodeData = {
  id: string;
  type: string;
};

type GraphEdgeData = {
  source: string;
  target: string;
  relationship: string;
  amount: number | null;
  timestamp: string | null;
};

type Analysis = {
  case_id: string;
  evidence: {
    cdr_records: number;
    bank_records: number;
    chat_evidence: boolean;
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
  };
  risk_analysis: {
    score: number;
    level: string;
    reasons: string[];
  };
};

const API_URL = "http://127.0.0.1:8000/analyze";

function EntityNode({ data }: NodeProps) {
  const nodeData = data as unknown as GraphNodeData;

  const type = nodeData.type;

  let icon = "☎";
  let typeLabel = "PHONE";

  if (type === "bank_account") {
    icon = "$";
    typeLabel = "BANK ACCOUNT";
  }

  if (type === "upi") {
    icon = "@";
    typeLabel = "UPI";
  }

  if (type === "ip") {
    icon = "◉";
    typeLabel = "IP ADDRESS";
  }

  return (
    <div className={`entity-node entity-${type}`}>
      <Handle
        type="target"
        position={Position.Left}
        className="custom-handle"
      />

      <div className="entity-icon">{icon}</div>

      <div className="entity-content">
        <div className="entity-id">{nodeData.id}</div>
        <div className="entity-type">{typeLabel}</div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="custom-handle"
      />
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

export default function Home() {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadAnalysis() {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(API_URL, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error("Backend returned an error");
      }

      const data = await response.json();

      setAnalysis(data);
    } catch (err) {
      console.error(err);
      setError(
        "Unable to connect to the FraudLens backend. Make sure FastAPI is running on port 8000."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAnalysis();
  }, []);

  const nodes = useMemo<Node[]>(() => {
    if (!analysis) return [];

    const graphNodes = analysis.graph.node_data;

    const banks = graphNodes.filter(
      (node) => node.type === "bank_account"
    );

    const upis = graphNodes.filter((node) => node.type === "upi");

    const phones = graphNodes.filter((node) => node.type === "phone");

    const ips = graphNodes.filter((node) => node.type === "ip");

    const result: Node[] = [];

    /*
      BANK ACCOUNT COLUMN
    */

    banks.forEach((node, index) => {
      result.push({
        id: node.id,
        type: "entity",
        position: {
          x: 80,
          y: 100 + index * 150,
        },
        data: node,
      });
    });

    /*
      UPI COLUMN
    */

    upis.forEach((node, index) => {
      result.push({
        id: node.id,
        type: "entity",
        position: {
          x: 550,
          y: 150 + index * 180,
        },
        data: node,
      });
    });

    /*
      PHONE COLUMN
    */

    phones.forEach((node, index) => {
      result.push({
        id: node.id,
        type: "entity",
        position: {
          x: 1020,
          y: 70 + index * 150,
        },
        data: node,
      });
    });

    /*
      IP COLUMN
    */

    ips.forEach((node, index) => {
      result.push({
        id: node.id,
        type: "entity",
        position: {
          x: 1020,
          y: 700 + index * 150,
        },
        data: node,
      });
    });

    return result;
  }, [analysis]);

  const edges = useMemo<Edge[]>(() => {
    if (!analysis) return [];

    return analysis.graph.edge_data.map((edge, index) => {
      const color = relationshipColor(edge.relationship);

      let label = edge.relationship;

      if (edge.amount !== null) {
        label = `${edge.relationship} ₹${edge.amount.toLocaleString("en-IN")}`;
      }

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

        style: {
          stroke: color,
          strokeWidth: relationshipWidth(edge.relationship),
        },

        labelStyle: {
          fill: "#e8edf7",
          fontSize: 11,
          fontWeight: 700,
        },

        labelBgStyle: {
          fill: "#07101d",
          fillOpacity: 0.95,
          stroke: color,
          strokeWidth: 1,
        },

        labelBgPadding: [6, 4],

        markerEnd: {
          type: "arrowclosed",
          color,
        },
      };
    });
  }, [analysis]);

  if (loading) {
    return (
      <main className="loading-screen">
        <div className="loading-box">
          <div className="loading-spinner" />
          <h2>FraudLens</h2>
          <p>Connecting to analysis engine...</p>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="error-screen">
        <div className="error-box">
          <div className="error-icon">!</div>
          <h1>Backend Connection Failed</h1>
          <p>{error}</p>

          <button onClick={loadAnalysis}>
            ↻ Retry Connection
          </button>
        </div>
      </main>
    );
  }

  if (!analysis) {
    return null;
  }

  const risk = analysis.risk_analysis.score;

  return (
    <main className="app">
      {/* HEADER */}

      <header className="header">
        <div className="brand">
          <div className="brand-mark">FL</div>

          <div>
            <div className="brand-name">FRAUDLENS</div>
            <div className="brand-subtitle">
              DIGITAL INVESTIGATION INTELLIGENCE
            </div>
          </div>
        </div>

        <div className="header-right">
          <div className="active-case">
            <span>ACTIVE CASE</span>
            <strong>{analysis.case_id}</strong>
          </div>

          <button className="refresh-button" onClick={loadAnalysis}>
            ↻ Refresh Analysis
          </button>
        </div>
      </header>

      {/* PAGE TITLE */}

      <section className="page-heading">
        <div>
          <div className="eyebrow">INVESTIGATION OVERVIEW</div>

          <h1>Digital Evidence Analysis</h1>
        </div>

        <div className="analysis-status">
          <span className="status-dot" />
          ANALYSIS ACTIVE
        </div>
      </section>

      {/* STAT CARDS */}

      <section className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">CDR RECORDS</div>
          <div className="stat-value">
            {analysis.evidence.cdr_records}
          </div>
          <div className="stat-description">
            Communication records
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">BANK RECORDS</div>
          <div className="stat-value">
            {analysis.evidence.bank_records}
          </div>
          <div className="stat-description">
            Financial transactions
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">ENTITIES</div>
          <div className="stat-value">
            {analysis.graph.nodes}
          </div>
          <div className="stat-description">
            Correlated entities
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">RELATIONSHIPS</div>
          <div className="stat-value">
            {analysis.graph.relationships}
          </div>
          <div className="stat-description">
            Detected connections
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">CHAT EVIDENCE</div>
          <div className="stat-value chat-value">
            {analysis.evidence.chat_evidence ? "YES" : "NO"}
          </div>
          <div className="stat-description">
            Communication evidence
          </div>
        </div>
      </section>

      {/* MAIN CONTENT */}

      <section className="main-grid">
        {/* GRAPH */}

        <div className="graph-panel">
          <div className="panel-header">
            <div>
              <div className="panel-eyebrow">CORRELATION ENGINE</div>

              <h2>Entity Relationship Graph</h2>
            </div>

            <div className="node-count">
              {analysis.graph.nodes} NODES
            </div>
          </div>

          <div className="graph-wrapper">
            <div className="graph-column-title bank-title">
              BANK ACCOUNTS
            </div>

            <div className="graph-column-title upi-title">
              UPI IDENTITIES
            </div>

            <div className="graph-column-title phone-title">
              PHONE ENTITIES
            </div>

            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{
                padding: 0.25,
              }}
              minZoom={0.4}
              maxZoom={1.5}
              nodesDraggable
              nodesConnectable={false}
              elementsSelectable
              proOptions={{
                hideAttribution: true,
              }}
            >
              <Background
                gap={32}
                size={1}
                color="#162033"
              />

              <Controls
                showInteractive={false}
              />

              <MiniMap
                nodeColor={(node) => {
                  const nodeData =
                    node.data as unknown as GraphNodeData;

                  if (nodeData.type === "bank_account") {
                    return "#5ca9ff";
                  }

                  if (nodeData.type === "upi") {
                    return "#e5a93d";
                  }

                  return "#45d6a3";
                }}
              />
            </ReactFlow>
          </div>

          {/* LEGEND */}

          <div className="graph-legend">
            <div className="legend-item">
              <span
                className="legend-line"
                style={{ background: "#5ca9ff" }}
              />
              CALL
            </div>

            <div className="legend-item">
              <span
                className="legend-line"
                style={{ background: "#e5a93d" }}
              />
              FINANCIAL
            </div>

            <div className="legend-item">
              <span
                className="legend-line"
                style={{ background: "#45d6a3" }}
              />
              CHAT LINK
            </div>
          </div>
        </div>

        {/* RISK PANEL */}

        <div className="risk-panel">
          <div className="panel-header">
            <div>
              <div className="panel-eyebrow">
                THREAT ASSESSMENT
              </div>

              <h2>Risk Analysis</h2>
            </div>
          </div>

          <div className="risk-content">
            <div className="risk-score-wrapper">
              <div
                className="risk-circle"
                style={
                  {
                    "--risk": `${risk}%`,
                  } as React.CSSProperties
                }
              >
                <div>
                  <strong>{risk}</strong>
                  <span>/ 100</span>
                </div>
              </div>

              <div className="risk-level">
                <span>RISK LEVEL</span>
                <strong>{analysis.risk_analysis.level}</strong>
              </div>
            </div>

            <div className="risk-bar">
              <div
                className="risk-bar-fill"
                style={{ width: `${risk}%` }}
              />
            </div>

            <div className="risk-reasons">
              <div className="reason-title">
                DETECTION REASONS
              </div>

              {analysis.risk_analysis.reasons.map(
                (reason, index) => (
                  <div className="reason" key={index}>
                    <span className="reason-icon">!</span>
                    <span>{reason}</span>
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      </section>

      {/* EVIDENCE SUMMARY */}

      <section className="evidence-section">
        <div className="panel-eyebrow">EVIDENCE CORRELATION</div>

        <h2>Investigation Evidence</h2>

        <div className="evidence-grid">
          <div className="evidence-box">
            <span>PHONE ENTITIES</span>
            <strong>{analysis.entities.phones.length}</strong>
          </div>

          <div className="evidence-box">
            <span>UPI IDENTITIES</span>
            <strong>{analysis.entities.upi_ids.length}</strong>
          </div>

          <div className="evidence-box">
            <span>BANK ACCOUNTS</span>
            <strong>
              {analysis.entities.bank_accounts.length}
            </strong>
          </div>

          <div className="evidence-box">
            <span>IP ADDRESSES</span>
            <strong>
              {analysis.entities.ip_addresses.length}
            </strong>
          </div>
        </div>
      </section>

      {/* RELATIONSHIP TABLE */}

      <section className="relationships-section">
        <div className="panel-eyebrow">RELATIONSHIP INTELLIGENCE</div>

        <h2>Detected Relationships</h2>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>SOURCE</th>
                <th>RELATIONSHIP</th>
                <th>TARGET</th>
                <th>AMOUNT</th>
                <th>TIMESTAMP</th>
              </tr>
            </thead>

            <tbody>
              {analysis.graph.edge_data.map((edge, index) => (
                <tr key={index}>
                  <td>{edge.source}</td>

                  <td>
                    <span
                      className={`relationship-badge relationship-${edge.relationship}`}
                    >
                      {edge.relationship}
                    </span>
                  </td>

                  <td>{edge.target}</td>

                  <td>
                    {edge.amount !== null
                      ? `₹${edge.amount.toLocaleString("en-IN")}`
                      : "—"}
                  </td>

                  <td>{edge.timestamp || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}