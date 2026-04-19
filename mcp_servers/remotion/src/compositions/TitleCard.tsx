/**
 * TitleCardComposition - Animated title card with keyword highlighting.
 *
 * Entry animation: fade-in + scale-up for title, staggered reveal for keywords.
 */

import React from "react";
import {
  AbsoluteFill,
  useVideoConfig,
  useTiming,
  interpolate,
  spring,
  Easing,
} from "remotion";
import type { TitleCardOptions } from "../types";
import { DEFAULT_TITLE_CARD } from "../types";

interface Props {
  options: TitleCardOptions;
}

export const TitleCard: React.FC<Props> = ({ options }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const { frame } = useTiming();

  const opts = { ...DEFAULT_TITLE_CARD, ...options };

  // Animation timeline (in frames)
  const entryDurationFrames = Math.round((opts.entryDuration ?? 1.0) * fps);
  const titleStartFrame = 0;
  const subtitleStartFrame = Math.round(entryDurationFrames * 0.5);
  const keywordStartFrame = Math.round(entryDurationFrames * 0.7);

  // Title animation: fade + scale
  const titleProgress = interpolate(
    frame,
    [titleStartFrame, titleStartFrame + entryDurationFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const titleScale = interpolate(titleProgress, [0, 1], [0.8, 1]);
  const titleOpacity = interpolate(titleProgress, [0, 0.3, 1], [0, 1, 1]);

  // Subtitle animation
  const subtitleProgress = interpolate(
    frame,
    [subtitleStartFrame, subtitleStartFrame + entryDurationFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const subtitleOpacity = interpolate(subtitleProgress, [0, 0.3, 1], [0, 1, 1]);

  // Keywords animation (staggered)
  const keywords = opts.keywords ?? [];
  const keywordAnimations = keywords.map((_, i) => {
    const startFrame = keywordStartFrame + i * 10;
    const progress = interpolate(
      frame,
      [startFrame, startFrame + entryDurationFrames],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    return {
      opacity: interpolate(progress, [0, 0.3, 1], [0, 1, 1]),
      translateY: interpolate(progress, [0, 1], [20, 0]),
    };
  });

  // Highlight the keywords in the title
  const highlightKeywords = (text: string): React.ReactNode => {
    if (!keywords.length) return text;

    const parts: React.ReactNode[] = [];
    let remaining = text;
    let keyIndex = 0;

    keywords.forEach((keyword) => {
      const idx = remaining.indexOf(keyword);
      if (idx !== -1) {
        if (idx > 0) {
          parts.push(<span key={`text-${keyIndex++}`}>{remaining.slice(0, idx)}</span>);
        }
        const anim = keywordAnimations[parts.length % keywordAnimations.length];
        parts.push(
          <span
            key={`kw-${keyIndex++}`}
            style={{
              color: opts.highlightColor,
              fontWeight: "bold",
              opacity: anim?.opacity ?? 1,
              transform: `translateY(${anim?.translateY ?? 0}px)`,
              display: "inline-block",
            }}
          >
            {keyword}
          </span>
        );
        remaining = remaining.slice(idx + keyword.length);
      }
    });

    if (remaining) {
      parts.push(<span key={`text-${keyIndex++}`}>{remaining}</span>);
    }

    return parts;
  };

  return (
    <AbsoluteFill
      style={{
        backgroundColor: opts.backgroundColor,
        justifyContent: "center",
        alignItems: "center",
        padding: 80,
      }}
    >
      <div
        style={{
          textAlign: "center",
          maxWidth: "80%",
        }}
      >
        {/* Title */}
        <div
          style={{
            fontSize: 96,
            fontFamily: opts.fontFamily ?? "Noto Sans SC, sans-serif",
            color: opts.textColor,
            fontWeight: "bold",
            marginBottom: 40,
            opacity: titleOpacity,
            transform: `scale(${titleScale})`,
            lineHeight: 1.2,
          }}
        >
          {highlightKeywords(opts.title)}
        </div>

        {/* Subtitle */}
        {opts.subtitle && (
          <div
            style={{
              fontSize: 48,
              fontFamily: opts.fontFamily ?? "Noto Sans SC, sans-serif",
              color: opts.textColor,
              opacity: subtitleOpacity * 0.8,
              marginBottom: 60,
            }}
          >
            {opts.subtitle}
          </div>
        )}

        {/* Keywords tags */}
        {keywords.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              justifyContent: "center",
              gap: 20,
            }}
          >
            {keywords.map((keyword, i) => (
              <div
                key={keyword}
                style={{
                  padding: "12px 24px",
                  backgroundColor: `${opts.highlightColor}20`,
                  border: `2px solid ${opts.highlightColor}`,
                  borderRadius: 30,
                  color: opts.highlightColor,
                  fontSize: 32,
                  fontFamily: opts.fontFamily ?? "Noto Sans SC, sans-serif",
                  opacity: keywordAnimations[i]?.opacity ?? 1,
                  transform: `translateY(${keywordAnimations[i]?.translateY ?? 0}px)`,
                }}
              >
                {keyword}
              </div>
            ))}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

export default TitleCard;
