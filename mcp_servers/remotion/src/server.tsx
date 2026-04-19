/**
 * MCP Server entry point for videoflow-remotion.
 *
 * This server exposes Remotion composition rendering as MCP tools.
 */

import React from "react";
import {
  serve,
  ListTools,
  CallTool,
  Server,
} from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  TitleCard,
  Chart,
  Diagram,
  Image,
  ScreenCapture,
  StockFootage,
} from "./compositions";
import {
  renderTitleCard,
  renderChart,
  renderDiagram,
  renderImage,
  renderScreenCapture,
  renderStockFootage,
} from "./lib/render";
import type {
  TitleCardOptions,
  ChartOptions,
  DiagramOptions,
  ImageOptions,
  ScreenCaptureOptions,
  StockFootageOptions,
  RemotionConfig,
} from "./types";
import { DEFAULT_CONFIG } from "./types";

// Server info
const SERVER_NAME = "videoflow-remotion";
const SERVER_VERSION = "0.2.0-dev.0";

// Create compositions map for dynamic rendering
const compositions = {
  TitleCard,
  Chart,
  Diagram,
  Image,
  ScreenCapture,
  StockFootage,
};

/**
 * Define the tool schemas for MCP.
 */
const tools = [
  {
    name: "render_title_card",
    description: "Render an animated title card with keyword highlighting and entry animation.",
    inputSchema: {
      type: "object",
      properties: {
        title: {
          type: "string",
          description: "Main title text",
        },
        subtitle: {
          type: "string",
          description: "Subtitle or description",
        },
        keywords: {
          type: "array",
          items: { type: "string" },
          description: "Keywords to highlight",
        },
        background_color: {
          type: "string",
          description: "Background color (hex, default: #0A1929)",
        },
        text_color: {
          type: "string",
          description: "Text color (hex, default: #FFFFFF)",
        },
        highlight_color: {
          type: "string",
          description: "Keyword highlight color (hex, default: #FFD700)",
        },
        entry_duration: {
          type: "number",
          description: "Entry animation duration in seconds (default: 1.0)",
        },
        output_path: {
          type: "string",
          description: "Output file path (optional, auto-generated if not provided)",
        },
        config: {
          type: "object",
          description: "Remotion config overrides",
          properties: {
            width: { type: "number" },
            height: { type: "number" },
            fps: { type: "number" },
            duration_in_seconds: { type: "number" },
          },
        },
      },
      required: ["title"],
    },
  },
  {
    name: "render_chart",
    description: "Render an animated chart (bar, line, pie, scatter).",
    inputSchema: {
      type: "object",
      properties: {
        type: {
          type: "string",
          enum: ["bar", "line", "pie", "scatter"],
          description: "Chart type",
        },
        data: {
          type: "array",
          items: {
            type: "object",
            properties: {
              label: { type: "string" },
              value: { type: "number" },
            },
            required: ["label", "value"],
          },
          description: "Data points",
        },
        title: {
          type: "string",
          description: "Chart title",
        },
        background_color: {
          type: "string",
          description: "Background color (hex)",
        },
        chart_color: {
          type: "string",
          description: "Chart color (hex)",
        },
        show_legend: {
          type: "boolean",
          description: "Show legend (default: true)",
        },
        animation_duration: {
          type: "number",
          description: "Animation duration in seconds (default: 2.0)",
        },
        output_path: {
          type: "string",
          description: "Output file path (optional)",
        },
        config: {
          type: "object",
          description: "Remotion config overrides",
          properties: {
            width: { type: "number" },
            height: { type: "number" },
            fps: { type: "number" },
            duration_in_seconds: { type: "number" },
          },
        },
      },
      required: ["type", "data"],
    },
  },
  {
    name: "render_diagram",
    description: "Render a Mermaid diagram with sequential animation.",
    inputSchema: {
      type: "object",
      properties: {
        mermaid_code: {
          type: "string",
          description: "Mermaid diagram syntax",
        },
        background_color: {
          type: "string",
          description: "Background color (hex)",
        },
        animation: {
          type: "string",
          enum: ["none", "fade", "sequential"],
          description: "Animation style (default: sequential)",
        },
        output_path: {
          type: "string",
          description: "Output file path (optional)",
        },
        config: {
          type: "object",
          description: "Remotion config overrides",
          properties: {
            width: { type: "number" },
            height: { type: "number" },
            fps: { type: "number" },
            duration_in_seconds: { type: "number" },
          },
        },
      },
      required: ["mermaid_code"],
    },
  },
  {
    name: "render_image",
    description: "Render an image with Ken Burns pan/zoom effect.",
    inputSchema: {
      type: "object",
      properties: {
        image_url: {
          type: "string",
          description: "Image URL",
        },
        caption: {
          type: "string",
          description: "Caption text",
        },
        caption_color: {
          type: "string",
          description: "Caption text color",
        },
        background_color: {
          type: "string",
          description: "Background color",
        },
        direction: {
          type: "string",
          enum: ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"],
          description: "Ken Burns direction (default: zoom_in)",
        },
        zoom_start: {
          type: "number",
          description: "Starting zoom (default: 1.0)",
        },
        zoom_end: {
          type: "number",
          description: "Ending zoom (default: 1.15)",
        },
        easing: {
          type: "string",
          enum: ["linear", "ease_in", "ease_out", "ease_in_out"],
          description: "Easing function (default: ease_in_out)",
        },
        output_path: {
          type: "string",
          description: "Output file path (optional)",
        },
        config: {
          type: "object",
          description: "Remotion config overrides",
          properties: {
            width: { type: "number" },
            height: { type: "number" },
            fps: { type: "number" },
            duration_in_seconds: { type: "number" },
          },
        },
      },
    },
  },
  {
    name: "render_screen_capture",
    description: "Render a screen capture with annotation overlays.",
    inputSchema: {
      type: "object",
      properties: {
        video_url: {
          type: "string",
          description: "URL to MP4 from Playwright",
        },
        video_path: {
          type: "string",
          description: "Local MP4 path",
        },
        viewport_width: {
          type: "number",
          description: "Browser viewport width (default: 1280)",
        },
        viewport_height: {
          type: "number",
          description: "Browser viewport height (default: 720)",
        },
        annotations: {
          type: "array",
          description: "Annotation overlays",
        },
        show_pointer: {
          type: "boolean",
          description: "Show pointer animation (default: true)",
        },
        background_color: {
          type: "string",
          description: "Background color",
        },
        output_path: {
          type: "string",
          description: "Output file path (optional)",
        },
        config: {
          type: "object",
          description: "Remotion config overrides",
          properties: {
            width: { type: "number" },
            height: { type: "number" },
            fps: { type: "number" },
            duration_in_seconds: { type: "number" },
          },
        },
      },
    },
  },
  {
    name: "render_stock_footage",
    description: "Render stock footage (Pexels) with Ken Burns effect.",
    inputSchema: {
      type: "object",
      properties: {
        video_url: {
          type: "string",
          description: "Video URL",
        },
        pexels_video_id: {
          type: "number",
          description: "Pexels video ID",
        },
        thumbnail_url: {
          type: "string",
          description: "Thumbnail/fallback image URL",
        },
        direction: {
          type: "string",
          enum: ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "random"],
          description: "Ken Burns direction (default: zoom_in)",
        },
        zoom_start: {
          type: "number",
          description: "Starting zoom (default: 1.0)",
        },
        zoom_end: {
          type: "number",
          description: "Ending zoom (default: 1.15)",
        },
        easing: {
          type: "string",
          enum: ["linear", "ease_in", "ease_out", "ease_in_out"],
          description: "Easing function (default: ease_in_out)",
        },
        caption: {
          type: "string",
          description: "Caption text",
        },
        caption_bg_color: {
          type: "string",
          description: "Caption background color",
        },
        caption_color: {
          type: "string",
          description: "Caption text color",
        },
        loop: {
          type: "boolean",
          description: "Loop video (default: true)",
        },
        background_color: {
          type: "string",
          description: "Background color",
        },
        output_path: {
          type: "string",
          description: "Output file path (optional)",
        },
        config: {
          type: "object",
          description: "Remotion config overrides",
          properties: {
            width: { type: "number" },
            height: { type: "number" },
            fps: { type: "number" },
            duration_in_seconds: { type: "number" },
          },
        },
      },
    },
  },
  {
    name: "list_compositions",
    description: "List available Remotion compositions.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
];

/**
 * Handle tool calls.
 */
async function handleToolCall(
  name: string,
  args: Record<string, unknown>
): Promise<{ content: Array<{ type: string; text: string }> }> {
  try {
    switch (name) {
      case "render_title_card": {
        const options: TitleCardOptions = {
          title: args.title as string,
          subtitle: args.subtitle as string | undefined,
          keywords: args.keywords as string[] | undefined,
          backgroundColor: args.background_color as string | undefined,
          textColor: args.text_color as string | undefined,
          highlightColor: args.highlight_color as string | undefined,
          entryDuration: args.entry_duration as number | undefined,
        };
        const config = args.config as Partial<RemotionConfig> | undefined;
        const outputPath = args.output_path as string | undefined;

        const result = await renderTitleCard(options, config, outputPath);

        return {
          content: [
            {
              type: "text",
              text: `Title card rendered successfully!\nOutput: ${result.outputPath}\nDuration: ${result.duration}s\nResolution: ${result.width}x${result.height}\nSize: ${(result.size / 1024 / 1024).toFixed(2)} MB`,
            },
          ],
        };
      }

      case "render_chart": {
        const options: ChartOptions = {
          type: args.type as ChartOptions["type"],
          data: args.data as ChartOptions["data"],
          title: args.title as string | undefined,
          backgroundColor: args.background_color as string | undefined,
          chartColor: args.chart_color as string | undefined,
          showLegend: args.show_legend as boolean | undefined,
          animationDuration: args.animation_duration as number | undefined,
        };
        const config = args.config as Partial<RemotionConfig> | undefined;
        const outputPath = args.output_path as string | undefined;

        const result = await renderChart(options, config, outputPath);

        return {
          content: [
            {
              type: "text",
              text: `Chart (${options.type}) rendered successfully!\nOutput: ${result.outputPath}\nDuration: ${result.duration}s\nResolution: ${result.width}x${result.height}\nSize: ${(result.size / 1024 / 1024).toFixed(2)} MB`,
            },
          ],
        };
      }

      case "list_compositions": {
        return {
          content: [
            {
              type: "text",
              text: `Available compositions:\n${Object.keys(compositions).join("\n")}`,
            },
          ],
        };
      }

      case "render_diagram": {
        const options: DiagramOptions = {
          mermaidCode: args.mermaid_code as string,
          backgroundColor: args.background_color as string | undefined,
          animation: args.animation as DiagramOptions["animation"],
        };
        const config = args.config as Partial<RemotionConfig> | undefined;
        const outputPath = args.output_path as string | undefined;

        const result = await renderDiagram(options, config, outputPath);

        return {
          content: [
            {
              type: "text",
              text: `Diagram rendered successfully!\nOutput: ${result.outputPath}\nDuration: ${result.duration}s\nResolution: ${result.width}x${result.height}\nSize: ${(result.size / 1024 / 1024).toFixed(2)} MB`,
            },
          ],
        };
      }

      case "render_image": {
        const options: ImageOptions = {
          imageUrl: args.image_url as string | undefined,
          caption: args.caption as string | undefined,
          captionColor: args.caption_color as string | undefined,
          backgroundColor: args.background_color as string | undefined,
          direction: args.direction as ImageOptions["direction"],
          zoomStart: args.zoom_start as number | undefined,
          zoomEnd: args.zoom_end as number | undefined,
          easing: args.easing as ImageOptions["easing"],
        };
        const config = args.config as Partial<RemotionConfig> | undefined;
        const outputPath = args.output_path as string | undefined;

        const result = await renderImage(options, config, outputPath);

        return {
          content: [
            {
              type: "text",
              text: `Image (Ken Burns) rendered successfully!\nOutput: ${result.outputPath}\nDuration: ${result.duration}s\nResolution: ${result.width}x${result.height}\nSize: ${(result.size / 1024 / 1024).toFixed(2)} MB`,
            },
          ],
        };
      }

      case "render_screen_capture": {
        const options: ScreenCaptureOptions = {
          videoUrl: args.video_url as string | undefined,
          videoPath: args.video_path as string | undefined,
          viewportWidth: args.viewport_width as number | undefined,
          viewportHeight: args.viewport_height as number | undefined,
          annotations: args.annotations as ScreenCaptureOptions["annotations"],
          showPointer: args.show_pointer as boolean | undefined,
          backgroundColor: args.background_color as string | undefined,
        };
        const config = args.config as Partial<RemotionConfig> | undefined;
        const outputPath = args.output_path as string | undefined;

        const result = await renderScreenCapture(options, config, outputPath);

        return {
          content: [
            {
              type: "text",
              text: `Screen capture rendered successfully!\nOutput: ${result.outputPath}\nDuration: ${result.duration}s\nResolution: ${result.width}x${result.height}\nSize: ${(result.size / 1024 / 1024).toFixed(2)} MB`,
            },
          ],
        };
      }

      case "render_stock_footage": {
        const options: StockFootageOptions = {
          videoUrl: args.video_url as string | undefined,
          pexelsVideoId: args.pexels_video_id as number | undefined,
          thumbnailUrl: args.thumbnail_url as string | undefined,
          direction: args.direction as StockFootageOptions["direction"],
          zoomStart: args.zoom_start as number | undefined,
          zoomEnd: args.zoom_end as number | undefined,
          easing: args.easing as StockFootageOptions["easing"],
          caption: args.caption as string | undefined,
          captionBgColor: args.caption_bg_color as string | undefined,
          captionColor: args.caption_color as string | undefined,
          loop: args.loop as boolean | undefined,
          backgroundColor: args.background_color as string | undefined,
        };
        const config = args.config as Partial<RemotionConfig> | undefined;
        const outputPath = args.output_path as string | undefined;

        const result = await renderStockFootage(options, config, outputPath);

        return {
          content: [
            {
              type: "text",
              text: `Stock footage rendered successfully!\nOutput: ${result.outputPath}\nDuration: ${result.duration}s\nResolution: ${result.width}x${result.height}\nSize: ${(result.size / 1024 / 1024).toFixed(2)} MB`,
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error instanceof Error ? error.message : String(error)}`,
        },
      ],
    };
  }
}

/**
 * Create and start the MCP server.
 */
async function main() {
  console.error("Starting videoflow-remotion MCP server...");

  const server = new Server(
    {
      name: SERVER_NAME,
      version: SERVER_VERSION,
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // Handle tool listing
  server.setRequestHandler(ListTools, async () => {
    return { tools };
  });

  // Handle tool calls
  server.setRequestHandler(CallTool, async (request) => {
    const { name, arguments: args } = request.params;
    return await handleToolCall(name, args ?? {});
  });

  // Start the server
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error("videoflow-remotion MCP server ready");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
