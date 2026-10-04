"use client";

// Thin wrapper so the parent can hold an imperative ref (zoom, fit, pause) while
// still loading this module via next/dynamic with ssr:false (dynamic() does not forward refs).
import ForceGraph2D from "react-force-graph-2d";

export default function ForceGraphCanvas({ graphRef, ...props }) {
  return <ForceGraph2D ref={graphRef} {...props} />;
}
