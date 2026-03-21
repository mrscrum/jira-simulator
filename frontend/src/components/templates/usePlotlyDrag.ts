import { useCallback, useRef } from "react";

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
  /** Get current plot-area bounds (container-relative pixels). null before first render. */
  getBounds: () => PlotAreaBounds | null;
  /** Convert a data-space x value to a container-relative pixel x. */
  xDataToPixel: (val: number) => number;
  /** Convert a container-relative pixel x to data-space x value. */
  xPixelToData: (px: number) => number;
  /** Convert a data-space y value to a container-relative pixel y. */
  yDataToPixel: (val: number) => number;
  /** Convert a container-relative pixel y to data-space y value. */
  yPixelToData: (px: number) => number;
  /** Category labels for x axis (if category axis), undefined otherwise. */
  getXCategories: () => string[] | undefined;
  /** Category labels for y axis (if category axis), undefined otherwise. */
  getYCategories: () => string[] | undefined;
}

/**
 * Hook that captures Plotly's internal axis coordinate system and exposes
 * data↔pixel conversion functions for positioning SVG overlays.
 *
 * IMPORTANT: All accessors are ref-based (no React state) to avoid
 * re-render loops with Plotly's onUpdate callback.
 *
 * Usage:
 *   const drag = usePlotlyDrag();
 *   <Plot onInitialized={drag.handlePlotUpdate} onUpdate={drag.handlePlotUpdate} ... />
 */
export function usePlotlyDrag(): PlotlyDragContext {
  const layoutRef = useRef<PlotlyLayout | null>(null);
  const boundsRef = useRef<PlotAreaBounds | null>(null);

  const handlePlotUpdate = useCallback((_figure: unknown, graphDiv: HTMLElement) => {
    const fl = (graphDiv as unknown as { _fullLayout?: PlotlyLayout })._fullLayout;
    if (!fl) return;
    layoutRef.current = fl;
    boundsRef.current = {
      left: fl._size.l,
      top: fl._size.t,
      width: fl._size.w,
      height: fl._size.h,
    };
  }, []);

  const getBounds = useCallback((): PlotAreaBounds | null => boundsRef.current, []);

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
    return fl._size.t + fl._size.h - fl.yaxis.d2p(val);
  }, []);

  const yPixelToData = useCallback((px: number): number => {
    const fl = layoutRef.current;
    if (!fl) return 0;
    return fl.yaxis.p2d(fl._size.h - (px - fl._size.t));
  }, []);

  const getXCategories = useCallback((): string[] | undefined =>
    layoutRef.current?.xaxis._categories, []);
  const getYCategories = useCallback((): string[] | undefined =>
    layoutRef.current?.yaxis._categories, []);

  return {
    handlePlotUpdate,
    getBounds,
    xDataToPixel,
    xPixelToData,
    yDataToPixel,
    yPixelToData,
    getXCategories,
    getYCategories,
  };
}
