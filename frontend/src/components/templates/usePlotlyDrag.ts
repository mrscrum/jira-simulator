import { useCallback, useRef, useState } from "react";

/** Pixel bounds of the Plotly plot area relative to the container element. */
export interface PlotAreaBounds {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface AxisFns {
  d2p: (v: number) => number;
  p2d: (v: number) => number;
  _categories?: string[];
}

interface PlotlyLayout {
  _size: { l: number; t: number; w: number; h: number };
  xaxis: AxisFns;
  yaxis: AxisFns;
}

export interface PlotlyDragContext {
  /** Ref callback for <Plot onInitialized / onUpdate> — call with (figure, graphDiv) */
  handlePlotUpdate: (figure: unknown, graphDiv: HTMLElement) => void;
  /** Current plot-area bounds (container-relative pixels). null before first render. */
  bounds: PlotAreaBounds | null;
  /** Convert a data-space x value to a container-relative pixel x. */
  xDataToPixel: (val: number) => number;
  /** Convert a container-relative pixel x to data-space x value. */
  xPixelToData: (px: number) => number;
  /** Convert a data-space y value to a container-relative pixel y. */
  yDataToPixel: (val: number) => number;
  /** Convert a container-relative pixel y to data-space y value. */
  yPixelToData: (px: number) => number;
  /** Category labels for x axis (if category axis), undefined otherwise. */
  xCategories: string[] | undefined;
  /** Category labels for y axis (if category axis), undefined otherwise. */
  yCategories: string[] | undefined;
}

/**
 * Hook that captures Plotly's internal axis coordinate system and exposes
 * data↔pixel conversion functions for positioning SVG overlays.
 *
 * Usage:
 *   const drag = usePlotlyDrag();
 *   <Plot onInitialized={drag.handlePlotUpdate} onUpdate={drag.handlePlotUpdate} ... />
 *   {drag.bounds && <svg style={{ position:'absolute', left: drag.bounds.left, ... }}>...</svg>}
 */
export function usePlotlyDrag(): PlotlyDragContext {
  const layoutRef = useRef<PlotlyLayout | null>(null);
  const [bounds, setBounds] = useState<PlotAreaBounds | null>(null);
  const [, setTick] = useState(0); // force re-render when layout changes

  const handlePlotUpdate = useCallback((_figure: unknown, graphDiv: HTMLElement) => {
    const fl = (graphDiv as unknown as { _fullLayout?: PlotlyLayout })._fullLayout;
    if (!fl) return;
    layoutRef.current = fl;
    const newBounds: PlotAreaBounds = {
      left: fl._size.l,
      top: fl._size.t,
      width: fl._size.w,
      height: fl._size.h,
    };
    setBounds(newBounds);
    setTick((t) => t + 1);
  }, []);

  const xDataToPixel = useCallback((val: number): number => {
    const fl = layoutRef.current;
    if (!fl) return 0;
    return fl._size.l + fl.xaxis.d2p(val);
  }, []);

  const xPixelToData = useCallback((px: number): number => {
    const fl = layoutRef.current;
    if (!fl) return 0;
    return fl.xaxis.p2d(px - fl._size.l);
  }, []);

  const yDataToPixel = useCallback((val: number): number => {
    const fl = layoutRef.current;
    if (!fl) return 0;
    // Plotly y-axis d2p returns offset from *bottom* of plot area (y increases up).
    // SVG y increases downward, so invert.
    return fl._size.t + fl._size.h - fl.yaxis.d2p(val);
  }, []);

  const yPixelToData = useCallback((px: number): number => {
    const fl = layoutRef.current;
    if (!fl) return 0;
    return fl.yaxis.p2d(fl._size.h - (px - fl._size.t));
  }, []);

  const xCategories = layoutRef.current?.xaxis._categories;
  const yCategories = layoutRef.current?.yaxis._categories;

  return {
    handlePlotUpdate,
    bounds,
    xDataToPixel,
    xPixelToData,
    yDataToPixel,
    yPixelToData,
    xCategories,
    yCategories,
  };
}
