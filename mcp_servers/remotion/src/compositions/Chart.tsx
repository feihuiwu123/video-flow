/**
 * ChartComposition - Animated chart with bar, line, pie, and scatter types.
 */

import React from "react";
import {
  AbsoluteFill,
  useVideoConfig,
  useTiming,
  interpolate,
  spring,
} from "remotion";
import type { ChartOptions, ChartDataPoint } from "../types";
import { DEFAULT_CHART } from "../types";

interface Props {
  options: ChartOptions;
}

export const Chart: React.FC<Props> = ({ options }) => {
  const { fps, width, height } = useVideoConfig();
  const { frame } = useTiming();

  const opts = { ...DEFAULT_CHART, ...options };

  const animationDurationFrames = Math.round((opts.animationDuration ?? 2.0) * fps);

  // Calculate max value for scaling
  const maxValue = Math.max(...opts.data.map((d) => d.value), 1);

  const renderBarChart = () => {
    const chartWidth = width * 0.8;
    const chartHeight = height * 0.5;
    const barWidth = chartWidth / opts.data.length - 20;
    const chartBottom = height * 0.75;
    const chartLeft = width * 0.1;

    return (
      <svg
        width={chartWidth}
        height={chartHeight}
        style={{ position: "absolute", left: chartLeft, top: chartBottom - chartHeight }}
      >
        {/* Y-axis line */}
        <line
          x1="0"
          y1={chartHeight}
          x2="0"
          y2="0"
          stroke={opts.chartColor}
          strokeWidth="2"
          opacity="0.5"
        />
        {/* X-axis line */}
        <line
          x1="0"
          y1={chartHeight}
          x2={chartWidth}
          y2={chartHeight}
          stroke={opts.chartColor}
          strokeWidth="2"
          opacity="0.5"
        />

        {/* Bars */}
        {opts.data.map((point, i) => {
          const barHeight = (point.value / maxValue) * chartHeight * 0.9;
          const x = i * (barWidth + 20) + 10;
          const animProgress = interpolate(
            frame,
            [i * 5, i * 5 + animationDurationFrames],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          const currentHeight = barHeight * animProgress;

          return (
            <g key={point.label}>
              <rect
                x={x}
                y={chartHeight - currentHeight}
                width={barWidth}
                height={currentHeight}
                fill={opts.chartColor}
                rx="4"
              />
              {/* Label */}
              <text
                x={x + barWidth / 2}
                y={chartHeight + 30}
                fill={opts.chartColor}
                fontSize="18"
                textAnchor="middle"
                fontFamily="Noto Sans SC, sans-serif"
              >
                {point.label}
              </text>
              {/* Value */}
              <text
                x={x + barWidth / 2}
                y={chartHeight - currentHeight - 10}
                fill={opts.chartColor}
                fontSize="16"
                textAnchor="middle"
                fontFamily="Noto Sans SC, sans-serif"
                fontWeight="bold"
              >
                {point.value.toFixed(0)}
              </text>
            </g>
          );
        })}
      </svg>
    );
  };

  const renderLineChart = () => {
    const chartWidth = width * 0.8;
    const chartHeight = height * 0.5;
    const chartBottom = height * 0.75;
    const chartLeft = width * 0.1;
    const points = opts.data.map((point, i) => ({
      x: chartLeft + (i / (opts.data.length - 1)) * chartWidth,
      y: chartBottom - (point.value / maxValue) * chartHeight * 0.9,
      value: point.value,
      label: point.label,
    }));

    const pathData = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
      .join(" ");

    // Calculate animated path
    const animProgress = interpolate(
      frame,
      [0, animationDurationFrames],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    const visiblePoints = Math.floor(points.length * animProgress);
    const animatedPathData = points
      .slice(0, visiblePoints)
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
      .join(" ");

    return (
      <svg
        width={chartWidth}
        height={chartHeight}
        style={{ position: "absolute", left: chartLeft, top: chartBottom - chartHeight }}
      >
        {/* Grid lines */}
        {[0.25, 0.5, 0.75, 1].map((ratio) => (
          <line
            key={ratio}
            x1="0"
            y1={chartHeight * (1 - ratio)}
            x2={chartWidth}
            y2={chartHeight * (1 - ratio)}
            stroke={opts.chartColor}
            strokeWidth="1"
            opacity="0.2"
            strokeDasharray="5,5"
          />
        ))}

        {/* Area fill */}
        <path
          d={`${animatedPathData} L ${points[visiblePoints - 1]?.x ?? 0} ${chartHeight} L 0 ${chartHeight} Z`}
          fill={opts.chartColor}
          opacity="0.2"
        />

        {/* Line */}
        <path
          d={animatedPathData}
          fill="none"
          stroke={opts.chartColor}
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Data points */}
        {points.slice(0, visiblePoints).map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="8" fill={opts.chartColor} />
            <circle cx={p.x} cy={p.y} r="4" fill="#0A1929" />
            <text
              x={p.x}
              y={chartHeight + 30}
              fill={opts.chartColor}
              fontSize="18"
              textAnchor="middle"
              fontFamily="Noto Sans SC, sans-serif"
            >
              {p.label}
            </text>
          </g>
        ))}
      </svg>
    );
  };

  const renderPieChart = () => {
    const centerX = width / 2;
    const centerY = height / 2 - 50;
    const radius = Math.min(width, height) * 0.3;

    const total = opts.data.reduce((sum, d) => sum + d.value, 0);
    const colors = [
      opts.chartColor,
      "#4CAF50",
      "#FF9800",
      "#E91E63",
      "#9C27B0",
      "#00BCD4",
    ];

    let currentAngle = -90;
    const animProgress = interpolate(
      frame,
      [0, animationDurationFrames],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    const slices = opts.data.map((point, i) => {
      const angle = (point.value / total) * 360 * animProgress;
      const startAngle = currentAngle;
      const endAngle = currentAngle + angle;
      currentAngle = endAngle;

      const startRad = (startAngle * Math.PI) / 180;
      const endRad = (endAngle * Math.PI) / 180;

      const x1 = centerX + radius * Math.cos(startRad);
      const y1 = centerY + radius * Math.sin(startRad);
      const x2 = centerX + radius * Math.cos(endRad);
      const y2 = centerY + radius * Math.sin(endRad);

      const largeArc = angle > 180 ? 1 : 0;

      const pathData = `M ${centerX} ${centerY} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`;

      return (
        <path
          key={point.label}
          d={pathData}
          fill={colors[i % colors.length]}
          stroke="#0A1929"
          strokeWidth="2"
        />
      );
    });

    return (
      <>
        <svg
          style={{ position: "absolute", left: 0, top: 0, width, height }}
        >
          {slices}
        </svg>

        {/* Legend */}
        <div
          style={{
            position: "absolute",
            bottom: height * 0.15,
            left: width * 0.1,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          {opts.data.map((point, i) => (
            <div
              key={point.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <div
                style={{
                  width: 20,
                  height: 20,
                  backgroundColor: colors[i % colors.length],
                  borderRadius: 4,
                }}
              />
              <span
                style={{
                  color: opts.chartColor,
                  fontSize: 24,
                  fontFamily: "Noto Sans SC, sans-serif",
                }}
              >
                {point.label}: {point.value}
              </span>
            </div>
          ))}
        </div>
      </>
    );
  };

  return (
    <AbsoluteFill
      style={{
        backgroundColor: opts.backgroundColor,
        padding: 40,
      }}
    >
      {/* Title */}
      {opts.title && (
        <div
          style={{
            position: "absolute",
            top: 40,
            left: 0,
            right: 0,
            textAlign: "center",
            color: opts.chartColor,
            fontSize: 48,
            fontFamily: "Noto Sans SC, sans-serif",
            fontWeight: "bold",
          }}
        >
          {opts.title}
        </div>
      )}

      {/* Chart */}
      <div
        style={{
          position: "absolute",
          top: 120,
          left: 0,
          right: 0,
          bottom: 0,
        }}
      >
        {opts.type === "bar" && renderBarChart()}
        {opts.type === "line" && renderLineChart()}
        {opts.type === "pie" && renderPieChart()}
      </div>
    </AbsoluteFill>
  );
};

export default Chart;
