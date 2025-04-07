'use client';

import React, { useState } from 'react';
import { TechnicalAnalysisResult } from '@/lib/connectors/llm';

interface TechnicalAnalysisCardProps {
  ticker: string;
  analysis: TechnicalAnalysisResult | null;
  provider: string;
  isLoading: boolean;
  error?: string;
}

export default function TechnicalAnalysisCard({ 
  ticker, 
  analysis, 
  provider, 
  isLoading,
  error 
}: TechnicalAnalysisCardProps) {
  const [activeTab, setActiveTab] = useState('summary');
  
  if (isLoading) {
    return (
      <div className="card w-full animate-pulse">
        <div className="p-6">
          <div className="h-8 bg-gray-200 rounded w-1/2 mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-4/5 mb-6"></div>
          <div className="h-48 bg-gray-200 rounded w-full"></div>
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="card w-full">
        <div className="p-6">
          <h2 className="text-xl font-semibold mb-2">Technical Analysis Error</h2>
          <p className="text-gray-600 mb-4">Unable to generate technical analysis for {ticker}</p>
          <div className="text-red-600">
            {error}
          </div>
        </div>
      </div>
    );
  }
  
  if (!analysis) {
    return (
      <div className="card w-full">
        <div className="p-6">
          <h2 className="text-xl font-semibold mb-2">No Analysis Available</h2>
          <p className="text-gray-600 mb-4">No technical analysis data available for {ticker}</p>
          <p>Try selecting a different ticker or refreshing the page.</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="card w-full">
      <div className="p-6">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xl font-semibold">Technical Analysis: {ticker}</h2>
          <span className="text-xs px-2 py-1 bg-gray-100 rounded-full capitalize">{provider}</span>
        </div>
        <p className="text-gray-600 mb-6">
          {analysis.summary}
        </p>
        
        <div className="w-full">
          <div className="flex border-b mb-6">
            <button 
              className={`px-4 py-2 font-medium ${activeTab === 'summary' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('summary')}
            >
              Summary
            </button>
            <button 
              className={`px-4 py-2 font-medium ${activeTab === 'trend' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('trend')}
            >
              Trend Analysis
            </button>
            <button 
              className={`px-4 py-2 font-medium ${activeTab === 'indicators' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('indicators')}
            >
              Indicators
            </button>
            <button 
              className={`px-4 py-2 font-medium ${activeTab === 'strategy' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('strategy')}
            >
              Strategy
            </button>
          </div>
          
          {activeTab === 'summary' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Overview</h3>
                <p className="text-sm text-gray-600">{analysis.summary}</p>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Trend Analysis</h3>
                <p className="text-sm text-gray-600">{analysis.trend_analysis?.primary_trend || 'N/A'} trend with {analysis.trend_analysis?.trend_strength || 'unknown'} strength</p>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Key Takeaways</h3>
                <ul className="list-disc pl-5 text-sm text-gray-600">
                  {[1, 2, 3].map((index) => (
                    <li key={index}>{analysis.summary}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          
          {activeTab === 'trend' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Short-Term Trend</h3>
                <p className="text-sm text-gray-600">{analysis.trend_analysis?.primary_trend || 'N/A'}</p>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Support Levels</h3>
                <p className="text-sm text-gray-600">
                  {analysis.support_resistance?.strong_support_levels?.join(', ') || 'N/A'}
                </p>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Resistance Levels</h3>
                <p className="text-sm text-gray-600">
                  {analysis.support_resistance?.strong_resistance_levels?.join(', ') || 'N/A'}
                </p>
              </div>
            </div>
          )}
          
          {activeTab === 'indicators' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-lg font-medium">RSI</h3>
                <p className="text-sm text-gray-600">
                  {analysis.indicator_analysis?.rsi?.condition || 'N/A'} ({analysis.indicator_analysis?.rsi?.value || 'N/A'})
                </p>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">MACD</h3>
                <p className="text-sm text-gray-600">
                  {analysis.indicator_analysis?.macd?.signal || 'N/A'} signal with {analysis.indicator_analysis?.macd?.strength || 'N/A'} strength
                </p>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Bollinger Bands</h3>
                <p className="text-sm text-gray-600">
                  Price at {analysis.indicator_analysis?.bollinger_bands?.position || 'N/A'} band
                </p>
              </div>
            </div>
          )}
          
          {activeTab === 'strategy' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Price Targets</h3>
                <p className="text-sm text-gray-600">
                  Short term: {analysis.price_targets?.short_term?.bullish_target || 'N/A'} (bullish) / {analysis.price_targets?.short_term?.bearish_target || 'N/A'} (bearish)
                </p>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Risk Assessment</h3>
                <p className="text-sm text-gray-600">
                  Stop loss: {analysis.risk_assessment?.optimal_stop_loss || 'N/A'}
                </p>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Risk Factors</h3>
                <ul className="list-disc pl-5 text-sm text-gray-600">
                  {analysis.risk_assessment?.key_risk_factors?.map((factor, index) => (
                    <li key={index}>{factor}</li>
                  )) || <li>No risk factors available</li>}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 