'use client';

import { TechnicalEvent } from '@/lib/connectors/yahoo-finance-insights';

interface TechnicalSignalsProps {
  signals: TechnicalEvent;
}

export default function TechnicalSignals({ signals }: TechnicalSignalsProps) {
  // Function to determine signal color based on content
  const getSignalColor = (signal: string) => {
    if (!signal) return 'text-gray-500';
    
    if (signal.toLowerCase().includes('bullish')) {
      return 'text-success-600';
    } else if (signal.toLowerCase().includes('bearish')) {
      return 'text-danger-600';
    } else {
      return 'text-warning-600'; // Neutral or other
    }
  };
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="card">
        <h3 className="text-lg font-medium mb-2">Short Term</h3>
        <div className={`text-xl font-bold ${getSignalColor(signals.shortTerm)}`}>
          {signals.shortTerm || 'N/A'}
        </div>
      </div>
      
      <div className="card">
        <h3 className="text-lg font-medium mb-2">Mid Term</h3>
        <div className={`text-xl font-bold ${getSignalColor(signals.midTerm)}`}>
          {signals.midTerm || 'N/A'}
        </div>
      </div>
      
      <div className="card">
        <h3 className="text-lg font-medium mb-2">Long Term</h3>
        <div className={`text-xl font-bold ${getSignalColor(signals.longTerm)}`}>
          {signals.longTerm || 'N/A'}
        </div>
      </div>
    </div>
  );
} 