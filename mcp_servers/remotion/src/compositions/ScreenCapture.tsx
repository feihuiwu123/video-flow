/**
 * ScreenCaptureComposition - Embed Playwright MP4 with annotation overlays.
 *
 * Shows recorded screen capture with optional annotations, highlights,
 * and pointer animations overlaid.
 */

import React, { useState, useEffect } from "react";
import {
  AbsoluteFill,
  useVideoConfig,
  useTiming,
  interpolate,
  spring,
} from "remotion";

interface Annotation {
  type: "highlight" | "arrow" | "text" | "circle";
  startFrame: number;
  endFrame: number;
  // Position (0-1 normalized)
  x: number;
  y: number;
  // Optional properties
  text?: string;
  color?: string;
  width?: number;
  height?: number;
  endX?: number;
  endY?: number;
}

interface Props {
  options: {
    /** URL to the MP4 from Playwright capture */
    videoUrl?: string;
    /** Path to local MP4 file */
    videoPath?: string;
    /** Browser viewport width (for aspect ratio) */
    viewportWidth?: number;
    /** Browser viewport height */
    viewportHeight?: number;
    /** Annotations to overlay */
    annotations?: Annotation[];
    /** Background color */
    backgroundColor?: string;
    /** Show pointer animation */
    showPointer?: boolean;
    /** Pointer path for animation (array of {x, y} normalized 0-1) */
    pointerPath?: Array<{ x: number; y: number }>;
  };
}

export const ScreenCapture: React.FC<Props> = ({ options }) => {
  const { fps, durationInFrames, width, height } = useVideoConfig();
  const { frame } = useTiming();

  const opts = {
    viewportWidth: 1280,
    viewportHeight: 720,
    backgroundColor: "#1a1a2e",
    showPointer: true,
    annotations: [],
    ...options,
  };

  // Calculate browser window dimensions to fit in output
  const aspectRatio = opts.viewportWidth / opts.viewportHeight;
  const outputAspectRatio = width / height;

  let browserWidth: number, browserHeight: number;
  if (aspectRatio > outputAspectRatio) {
    browserWidth = width * 0.85;
    browserHeight = browserWidth / aspectRatio;
  } else {
    browserHeight = height * 0.7;
    browserWidth = browserHeight * aspectRatio;
  }

  const browserX = (width - browserWidth) / 2;
  const browserY = (height - browserHeight) / 2;

  // Browser window animation
  const windowOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp" });

  // Render annotations
  const renderAnnotation = (annotation: Annotation, index: number) => {
    const progress = interpolate(
      frame,
      [annotation.startFrame, annotation.startFrame + 15],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    const endProgress = interpolate(
      frame,
      [annotation.endFrame - 15, annotation.endFrame],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    const opacity = Math.min(progress, endProgress);
    const absX = browserX + annotation.x * browserWidth;
    const absY = browserY + annotation.y * browserHeight;
    const absW = (annotation.width ?? 0.1) * browserWidth;
    const absH = (annotation.height ?? 0.05) * browserHeight;

    const color = annotation.color ?? "#FFD700";

    switch (annotation.type) {
      case "highlight":
        return (
          <div
            key={index}
            style={{
              position: "absolute",
              left: absX,
              top: absY,
              width: absW,
              height: absH,
              backgroundColor: color,
              opacity: opacity * 0.3,
              borderRadius: 4,
            }}
          />
        );
      case "circle":
        return (
          <div
            key={index}
            style={{
              position: "absolute",
              left: absX - absW / 2,
              top: absY - absH / 2,
              width: absW,
              height: absH,
              border: `3px solid ${color}`,
              borderRadius: "50%",
              opacity: opacity,
              boxShadow: `0 0 20px ${color}`,
            }}
          />
        );
      case "arrow":
        const endAbsX = browserX + (annotation.endX ?? annotation.x + 0.1) * browserWidth;
        const endAbsY = browserY + (annotation.endY ?? annotation.y + 0.05) * browserHeight;
        return (
          <svg
            key={index}
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              width: "100%",
              height: "100%",
              pointerEvents: "none",
            }}
          >
            <defs>
              <marker id={`arrowhead-${index}`} markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill={color} />
              </marker>
            </defs>
            <line
              x1={absX}
              y1={absY}
              x2={endAbsX}
              y2={endAbsY}
              stroke={color}
              strokeWidth="4"
              strokeDasharray={opacity < 1 ? "5,5" : undefined}
              markerEnd={`url(#arrowhead-${index})`}
              opacity={opacity}
            />
          </svg>
        );
      case "text":
        return (
          <div
            key={index}
            style={{
              position: "absolute",
              left: absX,
              top: absY,
              backgroundColor: color,
              color: "#000",
              padding: "8px 16px",
              borderRadius: 4,
              fontSize: 24,
              fontFamily: "Noto Sans SC, sans-serif",
              fontWeight: "bold",
              opacity: opacity,
              transform: `scale(${interpolate(opacity, [0, 1], [0.8, 1])})`,
            }}
          >
            {annotation.text}
          </div>
        );
      default:
        return null;
    }
  };

  // Pointer animation
  const renderPointer = () => {
    if (!opts.showPointer || !opts.pointerPath || opts.pointerPath.length === 0) {
      return null;
    }

    // Calculate pointer position along path
    const pathProgress = (frame / durationInFrames) * (opts.pointerPath.length - 1);
    const index = Math.floor(pathProgress);
    const nextIndex = Math.min(index + 1, opts.pointerPath.length - 1);
    const t = pathProgress - index;

    const x = opts.pointerPath[index].x + (opts.pointerPath[nextIndex].x - opts.pointerPath[index].x) * t;
    const y = opts.pointerPath[index].y + (opts.pointerPath[nextIndex].y - opts.pointerPath[index].y) * t;

    const pointerX = browserX + x * browserWidth;
    const pointerY = browserY + y * browserHeight;

    // Click animation
    const clickProgress = frame % 60 < 10 ? interpolate(frame % 60, [0, 10], [1, 1.5]) : 1;

    return (
      <div
        style={{
          position: "absolute",
          left: pointerX - 12,
          top: pointerY - 12,
          width: 24,
          height: 24,
          transform: `scale(${clickProgress})`,
          opacity: windowOpacity,
        }}
      >
        {/* Cursor SVG */}
        <svg viewBox="0 0 24 24" style={{ width: "100%", height: "100%" }}>
          <path
            d="M4 4L10 20L13 13L20 10L4 4Z"
            fill="#FFFFFF"
            stroke="#000000"
            strokeWidth="1.5"
          />
        </svg>
        {/* Click ripple */}
        <div
          style={{
            position: "absolute",
            inset: -4,
            border: "2px solid #FFD700",
            borderRadius: "50%",
            opacity: frame % 60 < 20 ? interpolate(frame % 60, [10, 20], [0.5, 0]) : 0,
          }}
        />
      </div>
    );
  };

  return (
    <AbsoluteFill
      style={{
        backgroundColor: opts.backgroundColor,
      }}
    >
      {/* Browser window */}
      <div
        style={{
          position: "absolute",
          left: browserX,
          top: browserY,
          width: browserWidth,
          height: browserHeight,
          backgroundColor: "#2d2d2d",
          borderRadius: 12,
          boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
          opacity: windowOpacity,
          overflow: "hidden",
        }}
      >
        {/* Browser header */}
        <div
          style={{
            height: 40,
            backgroundColor: "#3d3d3d",
            display: "flex",
            alignItems: "center",
            padding: "0 16px",
            gap: 8,
          }}
        >
          {/* Window controls */}
          <div style={{ display: "flex", gap: 6 }}>
            {["#ff5f57", "#ffbd2e", "#28c840"].map((color, i) => (
              <div
                key={i}
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  backgroundColor: color,
                }}
              />
            ))}
          </div>
          {/* URL bar */}
          <div
            style={{
              flex: 1,
              height: 28,
              backgroundColor: "#1a1a1a",
              borderRadius: 6,
              marginLeft: 16,
              display: "flex",
              alignItems: "center",
              padding: "0 12px",
            }}
          >
            <span style={{ color: "#888", fontSize: 12, fontFamily: "monospace" }}>
              {opts.videoUrl ?? "Screen Recording"}
            </span>
          </div>
        </div>

        {/* Video/content area */}
        <div
          style={{
            flex: 1,
            backgroundColor: "#1a1a1a",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {/* Video placeholder or actual video */}
          {opts.videoUrl ? (
            <video
              src={opts.videoUrl}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
              }}
            />
          ) : (
            <div
              style={{
                color: "#666",
                fontSize: 24,
                fontFamily: "monospace",
              }}
            >
              ▶ Screen Recording
            </div>
          )}
        </div>
      </div>

      {/* Annotations */}
      {opts.annotations?.map((annotation, i) => renderAnnotation(annotation, i))}

      {/* Pointer */}
      {renderPointer()}
    </AbsoluteFill>
  );
};

export default ScreenCapture;
