/**
 * Rendering utilities for Remotion compositions.
 */

import { renderMedia, still } from "@remotion/cli";
import { bundle } from "@remotion/bundler";
import path from "path";
import fs from "fs/promises";
import type {
  RemotionConfig,
  TitleCardOptions,
  ChartOptions,
  DiagramOptions,
  ImageOptions,
  ScreenCaptureOptions,
  StockFootageOptions,
  RenderResult,
} from "../types";
import { DEFAULT_CONFIG } from "../types";

const __dirname = new URL(".", import.meta.url).pathname;
const PROJECT_DIR = path.resolve(__dirname, "..");

/**
 * Get the bundle path, creating it if necessary.
 */
async function getBundlePath(): Promise<string> {
  const bundleDir = path.join(PROJECT_DIR, "dist", "bundle");

  try {
    await fs.access(bundleDir);
  } catch {
    console.log("Creating Remotion bundle...");
    await bundle({
      entryPoint: path.join(PROJECT_DIR, "src", "server.tsx"),
      onBundleProgress: (progress) => {
        console.log(`Bundling: ${Math.round(progress * 100)}%`);
      },
    });
  }

  return bundleDir;
}

/**
 * Render a composition by ID.
 */
async function renderComposition(
  compositionId: string,
  props: Record<string, unknown>,
  config: Partial<RemotionConfig>,
  outputPath: string
): Promise<RenderResult> {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  // Ensure output directory exists
  await fs.mkdir(path.dirname(outputPath), { recursive: true });

  const bundlePath = await getBundlePath();

  console.log(`Rendering ${compositionId}: ${outputPath}`);

  await renderMedia({
    composition: {
      id: compositionId,
      durationInFrames: Math.round(cfg.durationInSeconds * cfg.fps),
      fps: cfg.fps,
      width: cfg.width,
      height: cfg.height,
      props: props as never,
      defaultProps: {},
    },
    codec: "h264",
    outputLocation: outputPath,
    bundlePath: path.join(bundlePath, "remotionbundle.js"),
    inputProps: props,
  });

  const stats = await fs.stat(outputPath);

  return {
    outputPath,
    duration: cfg.durationInSeconds,
    width: cfg.width,
    height: cfg.height,
    size: stats.size,
  };
}

/**
 * Render a title card composition.
 */
export async function renderTitleCard(
  options: TitleCardOptions,
  config: Partial<RemotionConfig> = {},
  outputPath?: string
): Promise<RenderResult> {
  const outPath =
    outputPath ??
    path.join(PROJECT_DIR, "out", `titlecard_${Date.now()}.mp4`);

  return renderComposition("TitleCard", { options }, config, outPath);
}

/**
 * Render a chart composition.
 */
export async function renderChart(
  options: ChartOptions,
  config: Partial<RemotionConfig> = {},
  outputPath?: string
): Promise<RenderResult> {
  const outPath =
    outputPath ??
    path.join(PROJECT_DIR, "out", `chart_${Date.now()}.mp4`);

  return renderComposition("Chart", { options }, config, outPath);
}

/**
 * Render a diagram composition (Mermaid).
 */
export async function renderDiagram(
  options: DiagramOptions,
  config: Partial<RemotionConfig> = {},
  outputPath?: string
): Promise<RenderResult> {
  const outPath =
    outputPath ??
    path.join(PROJECT_DIR, "out", `diagram_${Date.now()}.mp4`);

  return renderComposition("Diagram", { options }, config, outPath);
}

/**
 * Render an image with Ken Burns effect.
 */
export async function renderImage(
  options: ImageOptions,
  config: Partial<RemotionConfig> = {},
  outputPath?: string
): Promise<RenderResult> {
  const outPath =
    outputPath ??
    path.join(PROJECT_DIR, "out", `image_${Date.now()}.mp4`);

  return renderComposition("Image", { options }, config, outPath);
}

/**
 * Render a screen capture with annotations.
 */
export async function renderScreenCapture(
  options: ScreenCaptureOptions,
  config: Partial<RemotionConfig> = {},
  outputPath?: string
): Promise<RenderResult> {
  const outPath =
    outputPath ??
    path.join(PROJECT_DIR, "out", `screencapture_${Date.now()}.mp4`);

  return renderComposition("ScreenCapture", { options }, config, outPath);
}

/**
 * Render stock footage with Ken Burns effect.
 */
export async function renderStockFootage(
  options: StockFootageOptions,
  config: Partial<RemotionConfig> = {},
  outputPath?: string
): Promise<RenderResult> {
  const outPath =
    outputPath ??
    path.join(PROJECT_DIR, "out", `stockfootage_${Date.now()}.mp4`);

  return renderComposition("StockFootage", { options }, config, outPath);
}

/**
 * Render a still frame (image) from a composition.
 */
export async function renderStill(
  compositionId: string,
  props: Record<string, unknown>,
  outputPath: string
): Promise<void> {
  const bundlePath = await getBundlePath();

  await still({
    composition: {
      id: compositionId,
      durationInFrames: 1,
      fps: 1,
      width: 1080,
      height: 1920,
      props: props as never,
      defaultProps: {},
    },
    outputLocation: outputPath,
    bundlePath: path.join(bundlePath, "remotionbundle.js"),
    inputProps: props,
    imageFormat: "png",
  });
}
