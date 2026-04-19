/**
 * StockFootageComposition - Pexels stock video with Ken Burns effect.
 *
 * Plays stock footage (from Pexels API) with cinematic Ken Burns
 * pan/zoom effect for smooth, professional-looking motion.
 */

import React, { useState, useEffect } from "react";
import {
  AbsoluteFill,
  useVideoConfig,
  useTiming,
  interpolate,
  Easing,
} from "remotion";

interface Props {
  options: {
    /** Pexels video ID or direct URL */
    videoUrl?: string;
    /** Pexels video ID */
    pexelsVideoId?: number;
    /** Thumbnail/fallback image URL */
    thumbnailUrl?: string;
    /** Ken Burns direction: "zoom_in" | "zoom_out" | "pan_left" | "pan_right" | "pan_up" | "pan_down" | "random" */
    direction?: string;
    /** Starting zoom level */
    zoomStart?: number;
    /** Ending zoom level */
    zoomEnd?: number;
    /** Easing: "linear" | "ease_in" | "ease_out" | "ease_in_out" */
    easing?: string;
    /** Caption text overlay */
    caption?: string;
    /** Caption background color */
    captionBgColor?: string;
    /** Caption text color */
    captionColor?: string;
    /** Loop the video */
    loop?: boolean;
    /** Background color while loading */
    backgroundColor?: string;
  };
}

export const StockFootage: React.FC<Props> = ({ options }) => {
  const { fps, durationInFrames, width, height } = useVideoConfig();
  const { frame } = useTiming();

  const opts = {
    direction: "zoom_in",
    zoomStart: 1.0,
    zoomEnd: 1.15,
    easing: "ease_in_out",
    loop: true,
    backgroundColor: "#000000",
    captionBgColor: "rgba(0,0,0,0.7)",
    captionColor: "#FFFFFF",
    ...options,
  };

  // Resolve actual direction (handle "random")
  const directions = ["zoom_in", "zoom_out", "pan_left", "pan_right"];
  const actualDirection =
    opts.direction === "random"
      ? directions[Math.floor(Math.random() * directions.length)]
      : opts.direction;

  // Calculate Ken Burns parameters
  const zoomStart = opts.zoomStart ?? 1.0;
  let zoomEnd = opts.zoomEnd ?? 1.15;
  let panX = 0;
  let panY = 0;

  if (actualDirection === "zoom_out") {
    zoomEnd = 0.85;
  } else if (actualDirection === "pan_left") {
    panX = -0.08;
    zoomEnd = zoomStart;
  } else if (actualDirection === "pan_right") {
    panX = 0.08;
    zoomEnd = zoomStart;
  } else if (actualDirection === "pan_up") {
    panY = -0.06;
    zoomEnd = zoomStart;
  } else if (actualDirection === "pan_down") {
    panY = 0.06;
    zoomEnd = zoomStart;
  }

  // Easing function
  const easing = opts.easing === "linear"
    ? Easing.linear
    : opts.easing === "ease_in"
    ? Easing.in(Easing.cubic)
    : opts.easing === "ease_out"
    ? Easing.out(Easing.cubic)
    : Easing.inOut(Easing.cubic);

  // Calculate animation progress
  const rawProgress = opts.loop ? (frame % durationInFrames) / durationInFrames : frame / durationInFrames;
  const progress = easing(rawProgress);

  // Calculate current zoom
  const currentZoom = zoomStart + (zoomEnd - zoomStart) * progress;

  // Calculate pan offset
  const offsetX = panX * progress * width;
  const offsetY = panY * progress * height;

  // Caption animation
  const captionOpacity = interpolate(
    frame,
    [0, 15, durationInFrames - 45, durationInFrames - 30],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Video progress (for progress bar)
  const videoProgress = rawProgress;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: opts.backgroundColor,
        overflow: "hidden",
      }}
    >
      {/* Video/image container with Ken Burns */}
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
        {opts.videoUrl ? (
          <video
            src={opts.videoUrl}
            autoPlay
            loop={opts.loop}
            muted
            playsInline
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        ) : opts.thumbnailUrl ? (
          <img
            src={opts.thumbnailUrl}
            alt="Stock footage"
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        ) : (
          <div
            style={{
              width: "100%",
              height: "100%",
              background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            }}
          />
        )}

        {/* Cinematic overlay */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `
              radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.4) 100%),
              linear-gradient(to bottom, rgba(0,0,0,0.2) 0%, transparent 15%, transparent 85%, rgba(0,0,0,0.3) 100%)
            `,
            pointerEvents: "none",
          }}
        />
      </div>

      {/* Caption overlay */}
      {opts.caption && captionOpacity > 0 && (
        <div
          style={{
            position: "absolute",
            bottom: 80,
            left: 60,
            right: 60,
            opacity: captionOpacity,
          }}
        >
          <div
            style={{
              backgroundColor: opts.captionBgColor,
              padding: "20px 32px",
              borderRadius: 8,
              borderLeft: `4px solid #FFD700`,
              maxWidth: 800,
            }}
          >
            <span
              style={{
                color: opts.captionColor,
                fontSize: 32,
                fontFamily: "Noto Sans SC, sans-serif",
                lineHeight: 1.5,
                textShadow: "0 2px 4px rgba(0,0,0,0.5)",
              }}
            >
              {opts.caption}
            </span>
          </div>
        </div>
      )}

      {/* Pexels attribution */}
      <div
        style={{
          position: "absolute",
          bottom: 20,
          right: 20,
          opacity: 0.6,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span style={{ color: "#fff", fontSize: 14, fontFamily: "sans-serif" }}>
          Videos provided by
        </span>
        <svg width="80" height="20" viewBox="0 0 80 20">
          <text x="0" y="15" fill="#fff" fontSize="14" fontWeight="bold">Pexels</text>
        </svg>
      </div>

      {/* Progress bar */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 4,
          backgroundColor: "rgba(255,255,255,0.2)",
        }}
      >
        <div
          style={{
            width: `${videoProgress * 100}%`,
            height: "100%",
            backgroundColor: "#FFD700",
          }}
        />
      </div>

      {/* Ken Burns indicator (subtle) */}
      <div
        style={{
          position: "absolute",
          top: 20,
          left: 20,
          opacity: 0.4,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="#fff" strokeWidth="2" />
          <circle cx="12" cy="12" r="6" stroke="#fff" strokeWidth="1.5" opacity="0.6" />
          <circle cx="12" cy="12" r="3" fill="#fff" opacity="0.8" />
        </svg>
        <span style={{ color: "#fff", fontSize: 12, fontFamily: "sans-serif" }}>
          {actualDirection.replace("_", " ")}
        </span>
      </div>
    </AbsoluteFill>
  );
};

export default StockFootage;
