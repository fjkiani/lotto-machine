'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { TimeSeriesPoint } from '@/lib/connectors/real-time-finance';

// Import Plotly dynamically to avoid SSR issues
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface TimeSeriesChartProps {
  data: TimeSeriesPoint[] | undefined | null;
  symbol: string;
  name?: string;
  price?: number;
  change?: number;
  changePercent?: number;
  period?: string;
  height?: number;
  width?: number;
  showVolume?: boolean;
  isLoading?: boolean;
}

export default function TimeSeriesChart({
  data,
  symbol,
  name = '',
  price = 0,
  change = 0,
  changePercent = 0,
  period = '1D',
  height = 500,
  width = 800,
  showVolume = true,
  isLoading = false
}: TimeSeriesChartProps) {
  const [plotData, setPlotData] = useState<any[]>([]);
  const [layout, setLayout] = useState<any>({});
  const [isReady, setIsReady] = useState(false);
  
  useEffect(() => {
    if (isLoading || !data || data.length === 0) {
      setIsReady(false);
      return;
    }
    
    // Process data for plotting
    const timestamps = data.map(point => new Date(point.datetime));
    const prices = data.map(point => point.close);
    const volumes = data.map(point => point.volume);
    
    // Check if we have valid data
    if (timestamps.length === 0 || prices.length === 0) {
      setIsReady(false);
      return;
    }
    
    // Create price trace
    const priceTrace = {
      type: 'scatter',
      mode: 'lines',
      name: 'Price',
      x: timestamps,
      y: prices,
      line: {
        color: change >= 0 ? '#22c55e' : '#ef4444',
        width: 2
      }
    };
    
    // Create chart data
    const chartData = [priceTrace];
    
    // Add volume bars if requested
    if (showVolume) {
      const volumeTrace = {
        type: 'bar',
        name: 'Volume',
        x: timestamps,
        y: volumes,
        yaxis: 'y2',
        marker: {
          color: volumes.map((_: number, i: number) => 
            (i > 0 && prices[i] > prices[i-1]) ? '#dcfce7' : '#fee2e2'
          ),
          line: {
            width: 0
          }
        },
        opacity: 0.5
      };
      
      chartData.push(volumeTrace);
    }
    
    // Calculate price range for Y-axis
    const minPrice = Math.min(...prices) * 0.995;
    const maxPrice = Math.max(...prices) * 1.005;
    
    // Calculate date format based on the period
    let tickFormat = '%H:%M';
    if (['5D', '1M', '3M'].includes(period)) {
      tickFormat = '%b %d';
    } else if (['6M', '1Y', '5Y', 'MAX'].includes(period)) {
      tickFormat = '%b %Y';
    }
    
    // Create chart layout
    const chartLayout = {
      title: `${symbol} - ${name || 'Price Chart'} (${period})`,
      showlegend: false,
      height: height,
      width: width,
      margin: { l: 50, r: 50, t: 70, b: 50 },
      xaxis: {
        type: 'date',
        tickformat: tickFormat,
        rangeslider: { visible: false }
      },
      yaxis: {
        title: 'Price',
        range: [minPrice, maxPrice],
        side: 'left',
        showgrid: true,
        zeroline: false
      },
      annotations: [{
        x: 0.05,
        y: 1.05,
        xref: 'paper',
        yref: 'paper',
        text: `Current: $${price.toFixed(2)} | ${change >= 0 ? '+' : ''}${change.toFixed(2)} (${(changePercent * 100).toFixed(2)}%)`,
        showarrow: false,
        font: {
          size: 12,
          color: change >= 0 ? '#22c55e' : '#ef4444'
        },
        bgcolor: 'rgba(255, 255, 255, 0.8)',
        bordercolor: change >= 0 ? '#22c55e' : '#ef4444',
        borderwidth: 1,
        borderpad: 4
      }]
    };
    
    // Add volume axis if requested
    if (showVolume) {
      // Calculate max volume for Y2 axis
      const maxVolume = Math.max(...volumes);
      
      chartLayout.yaxis2 = {
        title: 'Volume',
        range: [0, maxVolume * 4],
        side: 'right',
        overlaying: 'y',
        showgrid: false,
        zeroline: false
      };
    }
    
    setPlotData(chartData);
    setLayout(chartLayout);
    setIsReady(true);
  }, [data, symbol, name, price, change, changePercent, period, height, width, showVolume, isLoading]);
  
  if (!isReady) {
    return (
      <div className="flex justify-center items-center h-64 w-full">
        <p className="text-gray-500">Loading price chart...</p>
      </div>
    );
  }
  
  return (
    <div className="card p-0 overflow-hidden">
      <Plot
        data={plotData}
        layout={layout}
        config={{
          responsive: true,
          displayModeBar: true,
          modeBarButtonsToRemove: [
            'select2d', 'lasso2d', 'autoScale2d',
            'hoverClosestCartesian', 'hoverCompareCartesian'
          ]
        }}
        className="w-full"
      />
    </div>
  );
} 