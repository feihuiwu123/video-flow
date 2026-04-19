/**
 * Type definitions for videoflow-remotion MCP Server.
 */

export interface RemotionConfig {
  /** Output width in pixels (default: 1080) */
  width: number;
  /** Output height in pixels (default: 1920) */
  height: number;
  /** Frames per second (default: 30) */
  fps: number;
  /** Duration in seconds (default: 5) */
  durationInSeconds: number;
}

export interface TitleCardOptions {
  /** Main title text */
  title: string;
  /** Subtitle or description */
  subtitle?: string;
  /** Keywords to highlight */
  keywords?: string[];
  /** Background color (hex) */
  backgroundColor?: string;
  /** Text color (hex) */
  textColor?: string;
  /** Highlight color for keywords (hex) */
  highlightColor?: string;
  /** Entry animation duration in seconds */
  entryDuration?: number;
  /** Font family */
  fontFamily?: string;
}

export interface ChartDataPoint {
  label: string;
  value: number;
}

export interface ChartOptions {
  /** Chart title */
  title?: string;
  /** Chart type */
  type: "bar" | "line" | "pie" | "scatter";
  /** Data points */
  data: ChartDataPoint[];
  /** Background color (hex) */
  backgroundColor?: string;
  /** Chart color */
  chartColor?: string;
  /** Show legend */
  showLegend?: boolean;
  /** Animation duration in seconds */
  animationDuration?: number;
}

export interface DiagramOptions {
  /** Mermaid diagram code */
  mermaidCode: string;
  /** Background color (hex) */
  backgroundColor?: string;
  /** Animation style: "none" | "fade" | "sequential" */
  animation?: "none" | "fade" | "sequential";
}

export interface ImageOptions {
  /** Image URL */
  imageUrl?: string;
  /** Image caption */
  caption?: string;
  /** Caption text color */
  captionColor?: string;
  /** Background color */
  backgroundColor?: string;
  /** Ken Burns direction */
  direction?: "zoom_in" | "zoom_out" | "pan_left" | "pan_right" | "pan_up" | "pan_down";
  /** Starting zoom level */
  zoomStart?: number;
  /** Ending zoom level */
  zoomEnd?: number;
  /** Horizontal pan amount */
  panX?: number;
  /** Vertical pan amount */
  panY?: number;
  /** Easing function */
  easing?: "linear" | "ease_in" | "ease_out" | "ease_in_out";
  /** Show debug info */
  debug?: boolean;
}

export interface ScreenCaptureOptions {
  /** URL to MP4 from Playwright */
  videoUrl?: string;
  /** Local MP4 path */
  videoPath?: string;
  /** Viewport width */
  viewportWidth?: number;
  /** Viewport height */
  viewportHeight?: number;
  /** Annotations */
  annotations?: Annotation[];
  /** Background color */
  backgroundColor?: string;
  /** Show pointer */
  showPointer?: boolean;
  /** Pointer animation path */
  pointerPath?: Array<{ x: number; y: number }>;
}

export interface Annotation {
  type: "highlight" | "arrow" | "text" | "circle";
  startFrame: number;
  endFrame: number;
  x: number;
  y: number;
  text?: string;
  color?: string;
  width?: number;
  height?: number;
  endX?: number;
  endY?: number;
}

export interface StockFootageOptions {
  /** Video URL */
  videoUrl?: string;
  /** Pexels video ID */
  pexelsVideoId?: number;
  /** Thumbnail/fallback image */
  thumbnailUrl?: string;
  /** Ken Burns direction */
  direction?: "zoom_in" | "zoom_out" | "pan_left" | "pan_right" | "pan_up" | "pan_down" | "random";
  /** Starting zoom */
  zoomStart?: number;
  /** Ending zoom */
  zoomEnd?: number;
  /** Easing */
  easing?: "linear" | "ease_in" | "ease_out" | "ease_in_out";
  /** Caption text */
  caption?: string;
  /** Caption background */
  captionBgColor?: string;
  /** Caption text color */
  captionColor?: string;
  /** Loop video */
  loop?: boolean;
  /** Background color */
  backgroundColor?: string;
}

export interface RenderResult {
  /** Output file path */
  outputPath: string;
  /** Duration in seconds */
  duration: number;
  /** Output width */
  width: number;
  /** Output height */
  height: number;
  /** File size in bytes */
  size: number;
}

export const DEFAULT_CONFIG: RemotionConfig = {
  width: 1080,
  height: 1920,
  fps: 30,
  durationInSeconds: 5,
};

export const DEFAULT_TITLE_CARD: Omit<TitleCardOptions, "title"> = {
  backgroundColor: "#0A1929",
  textColor: "#FFFFFF",
  highlightColor: "#FFD700",
  entryDuration: 1.0,
  fontFamily: "Noto Sans SC",
};

export const DEFAULT_CHART: Omit<ChartOptions, "type" | "data"> = {
  backgroundColor: "#0A1929",
  chartColor: "#4FC3F7",
  showLegend: true,
  animationDuration: 2.0,
};

export const DEFAULT_DIAGRAM: Omit<DiagramOptions, "mermaidCode"> = {
  backgroundColor: "#0A1929",
  animation: "sequential",
};

export const DEFAULT_IMAGE: Omit<ImageOptions, never> = {
  direction: "zoom_in",
  zoomStart: 1.0,
  zoomEnd: 1.15,
  easing: "ease_in_out",
  captionColor: "#FFFFFF",
  backgroundColor: "#000000",
  debug: false,
};

export const DEFAULT_SCREEN_CAPTURE: Omit<ScreenCaptureOptions, never> = {
  viewportWidth: 1280,
  viewportHeight: 720,
  backgroundColor: "#1a1a2e",
  showPointer: true,
};

export const DEFAULT_STOCK_FOOTAGE: Omit<StockFootageOptions, never> = {
  direction: "zoom_in",
  zoomStart: 1.0,
  zoomEnd: 1.15,
  easing: "ease_in_out",
  loop: true,
  backgroundColor: "#000000",
  captionBgColor: "rgba(0,0,0,0.7)",
  captionColor: "#FFFFFF",
};
