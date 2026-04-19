/**
 * Remotion configuration for videoflow-remotion.
 *
 * This file configures the Remotion bundler and renderer.
 */

import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("png");
Config.setOverwriteOutput(true);

// Enable WebGL for better performance
Config.setShouldOpenBrowser(false);

// Bundle settings
Config.setPublicPath("dist/bundle");
Config.setEntryPoint("./src/server.tsx");
