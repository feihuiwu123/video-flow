/**
 * DiagramComposition - Mermaid SVG diagram with sequential animation.
 *
 * Animates diagram elements appearing one by one for storytelling effect.
 * Uses pre-rendered SVG from Mermaid CLI.
 */

import React, { useState, useEffect } from "react";
import {
  AbsoluteFill,
  useVideoConfig,
  useTiming,
  interpolate,
  spring,
} from "remotion";
import type { DiagramOptions } from "../types";
import { DEFAULT_DIAGRAM } from "../types";

interface Props {
  options: DiagramOptions;
}

export const Diagram: React.FC<Props> = ({ options }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const { frame } = useTiming();

  const opts = { ...DEFAULT_DIAGRAM, ...options };

  // Calculate animation timing
  const entryDurationFrames = Math.round(1.5 * fps); // 1.5s for full diagram
  const nodeCount = countNodes(opts.mermaidCode);
  const nodeAnimDuration = nodeCount > 0 ? (durationInFrames - entryDurationFrames) / nodeCount : durationInFrames;

  // Animation based on style
  let nodeProgress = 0;
  if (opts.animation === "sequential") {
    nodeProgress = interpolate(frame, [entryDurationFrames, durationInFrames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  } else if (opts.animation === "fade") {
    nodeProgress = interpolate(frame, [0, entryDurationFrames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  }

  // Overall opacity
  const opacity = opts.animation === "none" ? 1 : interpolate(nodeProgress, [0, 0.3, 1], [0, 1, 1]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: opts.backgroundColor,
        justifyContent: "center",
        alignItems: "center",
        padding: 40,
      }}
    >
      {/* Diagram SVG container */}
      <div
        style={{
          width: "90%",
          maxWidth: 1000,
          opacity,
          transform: `scale(${interpolate(opacity, [0, 1], [0.95, 1])})`,
        }}
      >
        {/* Placeholder SVG - in production, this would be the rendered Mermaid SVG */}
        <svg
          viewBox="0 0 800 600"
          style={{ width: "100%", height: "auto" }}
          dangerouslySetInnerHTML={{ __html: generatePlaceholderSVG(opts.mermaidCode, nodeProgress) }}
        />
      </div>

      {/* Animation indicator */}
      {opts.animation === "sequential" && (
        <div
          style={{
            position: "absolute",
            bottom: 40,
            left: "50%",
            transform: "translateX(-50%)",
            display: "flex",
            gap: 8,
          }}
        >
          {Array.from({ length: Math.min(nodeCount, 5) }).map((_, i) => {
            const nodeFrame = entryDurationFrames + i * nodeAnimDuration;
            const dotOpacity = interpolate(
              frame,
              [nodeFrame - 5, nodeFrame, nodeFrame + nodeAnimDuration * 0.7],
              [0.3, 1, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            return (
              <div
                key={i}
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  backgroundColor: "#64FFDA",
                  opacity: dotOpacity,
                }}
              />
            );
          })}
        </div>
      )}
    </AbsoluteFill>
  );
};

/**
 * Count approximate nodes in Mermaid code for animation timing.
 */
function countNodes(mermaidCode: string): number {
  // Rough estimation based on node indicators
  const patterns = [
    /\[.+?\]/g,      // [Square brackets]
    /\(.+?\)/g,      // (Parentheses)
    /\{.+?\}/g,      // {Curly braces}
    /-.->/g,         // Arrows
    /==>*/g,         // Thick arrows
  ];

  let count = 0;
  patterns.forEach((p) => {
    const matches = mermaidCode.match(p);
    if (matches) count += matches.length;
  });

  return Math.max(count, 1);
}

/**
 * Generate a placeholder SVG based on Mermaid code.
 * In production, this would be replaced with actual Mermaid rendering.
 */
function generatePlaceholderSVG(mermaidCode: string, progress: number): string {
  // Extract structure from Mermaid code for visualization
  const lines = mermaidCode.split("\n").filter((l) => l.trim() && !l.trim().startsWith("%"));

  return `
    <style>
      .node { fill: #1E3A5F; stroke: #64FFDA; stroke-width: 2; }
      .node-text { fill: #FFFFFF; font-family: 'Noto Sans SC', sans-serif; font-size: 14px; }
      .edge { stroke: #64FFDA; stroke-width: 2; fill: none; marker-end: url(#arrowhead); }
      .edge-animated { stroke-dasharray: 5,5; animation: dash 1s linear infinite; }
      @keyframes dash { to { stroke-dashoffset: -10; } }
    </style>
    <defs>
      <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
        <polygon points="0 0, 10 3.5, 0 7" fill="#64FFDA"/>
      </marker>
    </defs>
    <rect width="800" height="600" fill="#0A1929"/>
    <text x="400" y="50" text-anchor="middle" fill="#64FFDA" font-size="20" font-family="monospace">
      Mermaid Diagram
    </text>
    <g transform="translate(100, 80)">
      ${lines.map((line, i) => {
        const y = i * 60;
        const opacity = Math.min(1, Math.max(0, (progress * lines.length - i) / 2));
        if (line.includes("-->") || line.includes("->")) {
          return `<line x1="50" y1="${y - 30}" x2="250" y2="${y + 30}" class="edge" opacity="${opacity}"/>`;
        }
        return `
          <rect x="0" y="${y}" width="300" height="50" rx="8" class="node" opacity="${opacity}"/>
          <text x="150" y="${y + 30}" text-anchor="middle" class="node-text" opacity="${opacity}">${escapeXml(line.trim().slice(0, 20))}</text>
        `;
      }).join("")}
    </g>
  `;
}

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export default Diagram;
