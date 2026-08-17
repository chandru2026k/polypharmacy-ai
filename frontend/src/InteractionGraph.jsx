import { useMemo, useState } from "react";

const SEVERITY_COLOR = {
  High: "#e05252",
  Moderate: "#e0a852",
  Low: "#4caf6e",
};

/**
 * Renders the medication list as a small network graph:
 * - one node per unique drug (as entered by the user)
 * - one edge per found interaction, colored/thickness by severity
 * - nodes with no interactions are shown faded, so it's visually obvious
 *   which drugs in the list are "clean"
 *
 * Layout: simple circular placement (no physics simulation needed for
 * small medication lists, typically 2-8 drugs) — deterministic, always
 * readable, zero extra dependencies.
 */
export default function InteractionGraph({ results }) {
  const [hoveredEdge, setHoveredEdge] = useState(null);

  const { nodes, edges } = useMemo(() => {
    const drugSet = new Map(); // key: normalized name, value: display label

    results.forEach((r) => {
      drugSet.set(r.drug_1_normalized.normalized, r.drug_1);
      drugSet.set(r.drug_2_normalized.normalized, r.drug_2);
    });

    const drugKeys = Array.from(drugSet.keys());
    const n = drugKeys.length;
    const radius = 120;
    const centerX = 160;
    const centerY = 160;

    const nodes = drugKeys.map((key, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2;
      return {
        key,
        label: drugSet.get(key),
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
        hasInteraction: false,
      };
    });

    const nodeByKey = Object.fromEntries(nodes.map((node) => [node.key, node]));

    const edges = results
      .filter((r) => r.found)
      .map((r) => {
        const a = nodeByKey[r.drug_1_normalized.normalized];
        const b = nodeByKey[r.drug_2_normalized.normalized];
        if (a) a.hasInteraction = true;
        if (b) b.hasInteraction = true;
        return {
          id: `${r.drug_1}-${r.drug_2}`,
          a,
          b,
          severity: r.severity,
          confidence: r.confidence,
          drug_1: r.drug_1,
          drug_2: r.drug_2,
        };
      })
      .filter((e) => e.a && e.b);

    return { nodes, edges };
  }, [results]);

  if (nodes.length < 2) return null;

  return (
    <div className="graph-container">
      <h3 className="graph-title">Interaction Map</h3>
      <svg viewBox="0 0 320 320" className="graph-svg">
        {edges.map((edge) => {
          const color = SEVERITY_COLOR[edge.severity] || "#999";
          const isHovered = hoveredEdge === edge.id;
          const dashed = edge.confidence === "class_fallback";
          return (
            <g key={edge.id}>
              <line
                x1={edge.a.x}
                y1={edge.a.y}
                x2={edge.b.x}
                y2={edge.b.y}
                stroke={color}
                strokeWidth={isHovered ? 4 : 2.5}
                strokeDasharray={dashed ? "6,4" : undefined}
                opacity={isHovered ? 1 : 0.75}
                onMouseEnter={() => setHoveredEdge(edge.id)}
                onMouseLeave={() => setHoveredEdge(null)}
                style={{ cursor: "pointer" }}
              />
              {isHovered && (
                <text
                  x={(edge.a.x + edge.b.x) / 2}
                  y={(edge.a.y + edge.b.y) / 2 - 6}
                  textAnchor="middle"
                  className="graph-edge-label"
                >
                  {edge.severity}
                </text>
              )}
            </g>
          );
        })}

        {nodes.map((node) => (
          <g key={node.key}>
            <circle
              cx={node.x}
              cy={node.y}
              r={node.hasInteraction ? 16 : 12}
              fill={node.hasInteraction ? "#2f6f4f" : "#ccc"}
              stroke="white"
              strokeWidth={2}
            />
            <text
              x={node.x}
              y={node.y + (node.y > 160 ? 28 : -22)}
              textAnchor="middle"
              className="graph-node-label"
            >
              {node.label}
            </text>
          </g>
        ))}
      </svg>

      <div className="graph-legend">
        <span><span className="legend-dot" style={{ background: SEVERITY_COLOR.High }} /> High</span>
        <span><span className="legend-dot" style={{ background: SEVERITY_COLOR.Moderate }} /> Moderate</span>
        <span><span className="legend-dot" style={{ background: SEVERITY_COLOR.Low }} /> Low</span>
        <span className="legend-note">dashed line = class-level match</span>
      </div>
    </div>
  );
}