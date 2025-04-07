'use client';

import React, { useState } from 'react';
import { ComprehensiveAnalysisResult } from '@/lib/connectors/llm';

interface ComprehensiveAnalysisCardProps {
  ticker: string;
  analysis: ComprehensiveAnalysisResult | null;
  provider: string;
  isLoading: boolean;
  error?: string;
}

export default function ComprehensiveAnalysisCard({ 
  ticker, 
  analysis, 
  provider, 
  isLoading,
  error 
}: ComprehensiveAnalysisCardProps) {
  const [activeTab, setActiveTab] = useState('overview');
  
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
          <h2 className="text-xl font-semibold mb-2">Analysis Error</h2>
          <p className="text-gray-600 mb-4">Unable to generate comprehensive analysis for {ticker}</p>
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
          <p className="text-gray-600 mb-4">No comprehensive analysis data available for {ticker}</p>
          <p>Try selecting a different ticker or refreshing the page.</p>
        </div>
      </div>
    );
  }
  
  // Get ticker-specific analysis from the comprehensive result
  const tickerAnalysis = analysis.ticker_analysis?.[ticker.toUpperCase()];
  
  return (
    <div className="card w-full">
      <div className="p-6">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xl font-semibold">Comprehensive Analysis: {ticker}</h2>
          <span className="text-xs px-2 py-1 bg-gray-100 rounded-full capitalize">{provider}</span>
        </div>
        <div className="flex items-center space-x-2 mb-6">
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
            analysis.recommendation === 'buy' 
              ? 'bg-green-100 text-green-800' 
              : analysis.recommendation === 'sell' 
                ? 'bg-red-100 text-red-800' 
                : 'bg-yellow-100 text-yellow-800'
          }`}>
            {analysis.recommendation?.toUpperCase()}
          </span>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
            analysis.risk_level === 'low' 
              ? 'bg-green-100 text-green-800' 
              : analysis.risk_level === 'high' 
                ? 'bg-red-100 text-red-800' 
                : 'bg-yellow-100 text-yellow-800'
          }`}>
            {analysis.risk_level?.toUpperCase()} RISK
          </span>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
            analysis.market_sentiment === 'bullish' 
              ? 'bg-green-100 text-green-800' 
              : analysis.market_sentiment === 'bearish' 
                ? 'bg-red-100 text-red-800' 
                : 'bg-yellow-100 text-yellow-800'
          }`}>
            {analysis.market_sentiment?.toUpperCase()} SENTIMENT
          </span>
        </div>
        
        <div className="w-full">
          <div className="flex border-b mb-6 overflow-x-auto">
            <button 
              className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'overview' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('overview')}
            >
              Market Overview
            </button>
            <button 
              className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'ticker' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('ticker')}
            >
              Ticker Analysis
            </button>
            <button 
              className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'technical' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('technical')}
            >
              Technical Insights
            </button>
            <button 
              className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'learning' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('learning')}
            >
              Learning Points
            </button>
          </div>
          
          {activeTab === 'overview' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Market Sentiment</h3>
                <p className="text-sm text-gray-600">{analysis.market_overview?.summary || 'No market overview available'}</p>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Key Market Factors</h3>
                <ul className="list-disc pl-5 text-sm text-gray-600">
                  {analysis.market_overview?.key_factors?.map((factor, index) => (
                    <li key={index}>{factor}</li>
                  )) || <li>No key factors available</li>}
                </ul>
              </div>
            </div>
          )}
          
          {activeTab === 'ticker' && tickerAnalysis && (
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Current Position</h3>
                <p className="text-sm text-gray-600">
                  Current price: ${tickerAnalysis.current_price?.toFixed(2) || 'N/A'} ({tickerAnalysis.price_change_percent > 0 ? '+' : ''}{tickerAnalysis.price_change_percent?.toFixed(2) || 'N/A'}%)
                </p>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Technical Indicators</h3>
                <p className="text-sm text-gray-600">
                  {tickerAnalysis.technical_indicators?.trend || 'N/A'} with {tickerAnalysis.technical_indicators?.strength || 'N/A'} strength
                </p>
                
                <div className="mt-2">
                  <h4 className="text-sm font-medium">Key Levels:</h4>
                  <div className="flex flex-wrap gap-2 mt-1">
                    <div className="text-xs text-gray-600">
                      <span className="font-medium">Support:</span> {tickerAnalysis.technical_indicators?.key_levels?.support?.join(', ') || 'N/A'}
                    </div>
                    <div className="text-xs text-gray-600">
                      <span className="font-medium">Resistance:</span> {tickerAnalysis.technical_indicators?.key_levels?.resistance?.join(', ') || 'N/A'}
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Trading Strategy</h3>
                <p className="text-sm text-gray-600">{tickerAnalysis.recommendation} with {tickerAnalysis.confidence} confidence</p>
                <p className="text-sm text-gray-600 mt-1">{tickerAnalysis.rationale}</p>
                
                <div className="mt-2 grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-medium">Entry Points:</h4>
                    <p className="text-xs text-gray-600">{tickerAnalysis.trading_strategy?.entry_points?.join(', ') || 'N/A'}</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium">Exit Points:</h4>
                    <p className="text-xs text-gray-600">{tickerAnalysis.trading_strategy?.exit_points?.join(', ') || 'N/A'}</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium">Stop Loss:</h4>
                    <p className="text-xs text-gray-600">${tickerAnalysis.trading_strategy?.stop_loss || 'N/A'}</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium">Take Profit:</h4>
                    <p className="text-xs text-gray-600">${tickerAnalysis.trading_strategy?.take_profit || 'N/A'}</p>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {activeTab === 'technical' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Technical Insights</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {analysis.technical_insights?.map((insight, index) => (
                    <div key={index} className="p-3 border rounded-md">
                      <div className="flex justify-between items-start">
                        <h4 className="text-sm font-medium">{insight.indicator}</h4>
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                          insight.signal === 'bullish' 
                            ? 'bg-green-100 text-green-800' 
                            : insight.signal === 'bearish' 
                              ? 'bg-red-100 text-red-800' 
                              : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {insight.signal}
                        </span>
                      </div>
                      <p className="text-xs text-gray-600 mt-1">{insight.description}</p>
                    </div>
                  )) || (
                    <p className="text-sm text-gray-600">No technical insights available</p>
                  )}
                </div>
              </div>
            </div>
          )}
          
          {activeTab === 'learning' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-lg font-medium">Key Learning Points</h3>
                <ul className="list-disc pl-5 text-sm text-gray-600">
                  {analysis.learning_points?.map((point, index) => (
                    <li key={index}>{point}</li>
                  )) || <li>No learning points available</li>}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 