'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';

// Import Plotly dynamically to avoid SSR issues
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

// Define types for Plotly objects
interface ChartLayout {
  title: string;
  dragmode: string;
  showlegend: boolean;
  xaxis: {
    rangeslider: { visible: boolean };
    type: string;
  };
  yaxis: {
    title: string;
    autorange: boolean;
    fixedrange: boolean;
  };
  yaxis2?: {
    title: string;
    overlaying: string;
    side: string;
    showgrid: boolean;
  };
  height: number;
  margin: { l: number; r: number; t: number; b: number };
}

interface PriceChartProps {
  ticker: string;
  data: {
    dates: string[];
    open?: number[];
    high?: number[];
    low?: number[];
    close: number[];
    volume?: number[];
  };
  chartType?: 'candlestick' | 'line' | 'ohlc';
  showVolume?: boolean;
  height?: number;
}

export default function PriceChart({ 
  ticker, 
  data, 
  chartType = 'candlestick',
  showVolume = true,
  height = 600
}: PriceChartProps) {
  const [chartData, setChartData] = useState<any[]>([]);
  const [layout, setLayout] = useState<ChartLayout | null>(null);
  
  useEffect(() => {
    // Prepare the chart data based on the chart type
    const mainTrace: any = {};
    const volumeTrace: any = {};
    
    // Price trace
    if (chartType === 'candlestick' && data.open && data.high && data.low) {
      mainTrace.type = 'candlestick';
      mainTrace.x = data.dates;
      mainTrace.open = data.open;
      mainTrace.high = data.high;
      mainTrace.low = data.low;
      mainTrace.close = data.close;
      mainTrace.increasing = { line: { color: '#26a69a' } };
      mainTrace.decreasing = { line: { color: '#ef5350' } };
    } else if (chartType === 'ohlc' && data.open && data.high && data.low) {
      mainTrace.type = 'ohlc';
      mainTrace.x = data.dates;
      mainTrace.open = data.open;
      mainTrace.high = data.high;
      mainTrace.low = data.low;
      mainTrace.close = data.close;
      mainTrace.increasing = { line: { color: '#26a69a' } };
      mainTrace.decreasing = { line: { color: '#ef5350' } };
    } else {
      // Default to line chart if candlestick data not available
      mainTrace.type = 'scatter';
      mainTrace.mode = 'lines';
      mainTrace.x = data.dates;
      mainTrace.y = data.close;
      mainTrace.name = ticker;
      mainTrace.line = { color: '#2196f3', width: 2 };
    }
    
    // Volume trace
    if (showVolume && data.volume) {
      volumeTrace.type = 'bar';
      volumeTrace.x = data.dates;
      volumeTrace.y = data.volume;
      volumeTrace.name = 'Volume';
      volumeTrace.marker = { color: 'rgba(100, 100, 255, 0.3)' };
      volumeTrace.yaxis = 'y2';
    }
    
    // Set chart data
    const newChartData = [mainTrace];
    if (showVolume && data.volume) {
      newChartData.push(volumeTrace);
    }
    setChartData(newChartData);
    
    // Set layout
    const newLayout: ChartLayout = {
      title: `${ticker} Price Chart`,
      dragmode: 'zoom',
      showlegend: false,
      xaxis: {
        rangeslider: { visible: false },
        type: 'date',
      },
      yaxis: {
        title: 'Price',
        autorange: true,
        fixedrange: false,
      },
      height: height,
      margin: { l: 50, r: 20, t: 50, b: 50 },
    };
    
    if (showVolume && data.volume) {
      newLayout.yaxis2 = {
        title: 'Volume',
        overlaying: 'y',
        side: 'right',
        showgrid: false,
      };
    }
    
    setLayout(newLayout);
  }, [ticker, data, chartType, showVolume, height]);
  
  // If layout is not set yet, show loading
  if (!layout || chartData.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <p>Loading chart data...</p>
      </div>
    );
  }
  
  return (
    <div className="w-full h-full">
      <Plot
        data={chartData}
        layout={layout}
        config={{ responsive: true }}
        className="w-full h-full"
      />
    </div>
  );
} 