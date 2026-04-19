/**
 * ImageComposition - Ken Burns effect on static images.
 *
 * Provides smooth pan/zoom animations for still images to create
 * cinematic motion without actual video footage.
 */

import React from "react";
import {
  AbsoluteFill,
  useVideoConfig,
  useTiming,
  interpolate,
  Easing,
} from "remotion";
import type { ImageOptions } from "../types";
import { DEFAULT_IMAGE } from "../types";

interface Props {
  options: ImageOptions;
}

export const Image: React.FC<Props> = ({ options }) => {
  const { fps, durationInFrames, width, height } = useVideoConfig();
  const { frame } = useTiming();

  const opts = { ...DEFAULT_IMAGE, ...options };

  // Calculate animation parameters
  const zoomStart = opts.zoomStart ?? 1.0;
  const zoomEnd = opts.zoomEnd ?? (opts.direction === "zoom_in" ? 1.2 : opts.direction === "zoom_out" ? 0.8 : 1.0);
  const panX = opts.panX ?? (opts.direction === "pan_left" ? 0.05 : opts.direction === "pan_right" ? -0.05 : 0);
  const panY = opts.panY ?? (opts.direction === "pan_up" ? 0.05 : opts.direction === "pan_down" ? -0.05 : 0);

  // Easing function
  const easing = opts.easing === "linear"
    ? Easing.linear
    : opts.easing === "ease_in"
    ? Easing.in(Easing.quad)
    : opts.easing === "ease_out"
    ? Easing.out(Easing.quad)
    : Easing.inOut(Easing.cubic);

  // Calculate current progress with easing
  const rawProgress = frame / durationInFrames;
  const progress = easing(rawProgress);

  // Calculate zoom
  const currentZoom = zoomStart + (zoomEnd - zoomStart) * progress;

  // Calculate pan offset
  const offsetX = panX * progress * width;
  const offsetY = panY * progress * height;

  // Overlay text/caption if provided
  const captionOpacity = interpolate(
    frame,
    [durationInFrames * 0.7, durationInFrames * 0.8],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        backgroundColor: opts.backgroundColor ?? "#000000",
      }}
    >
      {/* Ken Burns image container */}
      <div
        style={{
          position: "absolute",
          width: width * currentZoom,
          height: height * currentZoom,
          left: "50%",
          top: "50%",
          transform: `translate(calc(-50% + ${offsetX}px), calc(-50% + ${offsetY}px))`,
        }}
      >
        {/* Image element - uses provided URL or placeholder */}
        {opts.imageUrl ? (
          <img
            src={opts.imageUrl}
            alt="Ken Burns"
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        ) : (
          /* Placeholder gradient */
          <div
            style={{
              width: "100%",
              height: "100%",
              background: `linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)`,
            }}
          />
        )}

        {/* Vignette overlay */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.6) 100%)`,
            pointerEvents: "none",
          }}
        />
      </div>

      {/* Optional caption overlay */}
      {opts.caption && captionOpacity > 0 && (
        <div
          style={{
            position: "absolute",
            bottom: 60,
            left: 60,
            right: 60,
            opacity: captionOpacity,
          }}
        >
          <div
            style={{
              backgroundColor: "rgba(0, 0, 0, 0.7)",
              padding: "16px 24px",
              borderRadius: 8,
              borderLeft: `4px solid ${opts.captionColor ?? "#FFD700"}`,
            }}
          >
            <span
              style={{
                color: opts.captionColor ?? "#FFFFFF",
                fontSize: 28,
                fontFamily: "Noto Sans SC, sans-serif",
                lineHeight: 1.4,
              }}
            >
              {opts.caption}
            </span>
          </div>
        </div>
      )}

      {/* Ken Burns direction indicator (debug, hidden by default) */}
      {opts.debug && (
        <div
          style={{
            position: "absolute",
            top: 20,
            right: 20,
            backgroundColor: "rgba(255,255,255,0.9)",
            padding: "8px 16px",
            borderRadius: 4,
            fontSize: 12,
            fontFamily: "monospace",
          }}
        >
          Direction: {opts.direction} | Zoom: {currentZoom.toFixed(3)} | Pan: ({offsetX.toFixed(0)}, {offsetY.toFixed(0)})
        </div>
      )}
    </AbsoluteFill>
  );
};

export default Image;
