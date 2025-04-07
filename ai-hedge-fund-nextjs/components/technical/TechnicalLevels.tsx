'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { KeyTechnical } from '@/lib/connectors/yahoo-finance-insights';

// Import Plotly dynamically to avoid SSR issues
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface TechnicalLevelsProps {
  levels: KeyTechnical;
  currentPrice: number;
}

interface ChartLayout {
  title: string;
  showlegend: boolean;
  yaxis: {
    title: string;
    range?: number[];
  };
  height: number;
  width: number;
  annotations: any[];
  shapes: any[];
}

export default function TechnicalLevels({ levels, currentPrice }: TechnicalLevelsProps) {
  const [chartData, setChartData] = useState<any[]>([]);
  const [layout, setLayout] = useState<ChartLayout | null>(null);
  
  useEffect(() => {
    if (!levels) return;
    
    // Prepare data for visualization
    const dataPoint = {
      x: ['Current Price'],
      y: [currentPrice],
      type: 'scatter',
      mode: 'markers',
      marker: {
        color: 'blue',
        size: 12
      },
      name: 'Current Price'
    };
    
    setChartData([dataPoint]);
    
    // Calculate min and max for Y axis
    const values = [
      currentPrice,
      levels.support, 
      levels.resistance, 
      levels.stopLoss
    ].filter(v => v > 0);
    
    const minVal = Math.min(...values) * 0.95;
    const maxVal = Math.max(...values) * 1.05;
    
    // Prepare annotations and shapes
    const annotations = [];
    const shapes = [];
    
    // Support line (green)
    if (levels.support > 0) {
      shapes.push({
        type: 'line',
        x0: -0.5,
        x1: 0.5, 
        y0: levels.support,
        y1: levels.support,
        line: {
          color: 'green',
          width: 2,
          dash: 'solid'
        }
      });
      
      annotations.push({
        x: 0.5,
        y: levels.support,
        xref: 'x',
        yref: 'y',
        text: `Support: ${levels.support.toFixed(2)}`,
        showarrow: true,
        arrowhead: 2,
        ax: 60,
        ay: 0,
        bgcolor: 'rgba(255, 255, 255, 0.8)',
        font: { color: 'green' }
      });
    }
    
    // Resistance line (red)
    if (levels.resistance > 0) {
      shapes.push({
        type: 'line',
        x0: -0.5,
        x1: 0.5,
        y0: levels.resistance,
        y1: levels.resistance,
        line: {
          color: 'red',
          width: 2,
          dash: 'solid'
        }
      });
      
      annotations.push({
        x: 0.5,
        y: levels.resistance,
        xref: 'x',
        yref: 'y',
        text: `Resistance: ${levels.resistance.toFixed(2)}`,
        showarrow: true,
        arrowhead: 2,
        ax: 70,
        ay: 0,
        bgcolor: 'rgba(255, 255, 255, 0.8)',
        font: { color: 'red' }
      });
    }
    
    // Stop Loss line (orange)
    if (levels.stopLoss > 0) {
      shapes.push({
        type: 'line',
        x0: -0.5,
        x1: 0.5,
        y0: levels.stopLoss,
        y1: levels.stopLoss,
        line: {
          color: 'orange',
          width: 2,
          dash: 'dash'
        }
      });
      
      annotations.push({
        x: 0.5,
        y: levels.stopLoss,
        xref: 'x',
        yref: 'y',
        text: `Stop Loss: ${levels.stopLoss.toFixed(2)}`,
        showarrow: true,
        arrowhead: 2,
        ax: 65,
        ay: 0,
        bgcolor: 'rgba(255, 255, 255, 0.8)',
        font: { color: 'orange' }
      });
    }
    
    // Set chart layout
    setLayout({
      title: 'Key Technical Levels',
      showlegend: false,
      yaxis: {
        title: 'Price',
        range: [minVal, maxVal]
      },
      height: 400,
      width: 600,
      annotations: annotations,
      shapes: shapes
    });
  }, [levels, currentPrice]);
  
  // If layout is not set yet, show loading
  if (!layout || chartData.length === 0) {
    return (
      <div className="w-full h-64 flex items-center justify-center">
        <p>Loading technical levels...</p>
      </div>
    );
  }
  
  return (
    <div className="card p-0 overflow-hidden">
      <Plot
        data={chartData}
        layout={layout}
        config={{ responsive: true }}
        className="w-full"
      />
    </div>
  );
} 