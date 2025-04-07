declare module 'react-plotly.js' {
  import * as React from 'react';
  
  interface PlotParams {
    data?: any[];
    layout?: any;
    config?: any;
    frames?: any[];
    className?: string;
    style?: React.CSSProperties;
    onInitialized?: (figure: any, graphDiv: HTMLElement) => void;
    onUpdate?: (figure: any, graphDiv: HTMLElement) => void;
    onPurge?: (figure: any, graphDiv: HTMLElement) => void;
    onError?: (err: Error) => void;
    onAfterPlot?: (figure: any, graphDiv: HTMLElement) => void;
    onRedraw?: (figure: any, graphDiv: HTMLElement) => void;
    onSelected?: (event: any) => void;
    onDeselect?: (event: any) => void;
    onSelecting?: (event: any) => void;
    onDoubleClick?: (event: any) => void;
    onClick?: (event: any) => void;
    onHover?: (event: any) => void;
    onUnhover?: (event: any) => void;
    onLegendClick?: (event: any) => boolean;
    onLegendDoubleClick?: (event: any) => boolean;
    onRelayout?: (event: any) => void;
    onRestyle?: (event: any) => void;
    onRelayouting?: (event: any) => void;
    onResize?: (figure: any, graphDiv: HTMLElement) => void;
    onSliderChange?: (event: any) => void;
    onSliderEnd?: (event: any) => void;
    onSliderStart?: (event: any) => void;
    onAnimated?: (event: any) => void;
    onAnimatingFrame?: (event: any) => void;
    onAddTrace?: (figure: any, graphDiv: HTMLElement) => void;
    onDeleteTrace?: (figure: any, graphDiv: HTMLElement) => void;
    onTypeChange?: (figure: any, graphDiv: HTMLElement) => void;
    onUpdated?: (e: any) => void;
    divId?: string;
    debug?: boolean;
    useResizeHandler?: boolean;
    revision?: number;
  }
  
  const Plot: React.ComponentType<PlotParams>;
  
  export default Plot;
} 