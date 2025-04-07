'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import TechnicalAnalysisCard from '@/components/analysis/TechnicalAnalysisCard';
import ComprehensiveAnalysisCard from '@/components/analysis/ComprehensiveAnalysisCard';
import useAnalysis, { AnalysisType, AnalysisProvider } from '@/hooks/useAnalysis';
import TimeSeriesChart from '@/components/charts/TimeSeriesChart';
import useTimeSeries from '@/hooks/useTimeSeries';
import { useMarketData } from '@/hooks/useMarketData';

export default function AnalysisPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // Get initial values from URL parameters or use defaults
  const initialTicker = searchParams.get('ticker') || 'AAPL';
  const initialAnalysisType = (searchParams.get('type') as AnalysisType) || 'technical';
  const initialProvider = (searchParams.get('provider') as AnalysisProvider) || 'openai';
  const initialPeriod = searchParams.get('period') || '1M';
  
  // State for form values
  const [ticker, setTicker] = useState(initialTicker);
  const [inputTicker, setInputTicker] = useState(initialTicker);
  const [analysisType, setAnalysisType] = useState<AnalysisType>(initialAnalysisType);
  const [provider, setProvider] = useState<AnalysisProvider>(initialProvider);
  const [period, setPeriod] = useState(initialPeriod);
  
  // Fetch analysis data
  const { analysis, isLoading: isAnalysisLoading, error: analysisError } = useAnalysis({
    ticker,
    type: analysisType,
    provider,
    period
  });
  
  // Fetch time series data for chart
  const { data: timeSeriesData, isLoading: isTimeSeriesLoading } = useTimeSeries(ticker, period);
  
  // Fetch market data for company info
  const { data: marketData } = useMarketData(ticker);
  
  // Update URL with current parameters
  useEffect(() => {
    const params = new URLSearchParams();
    params.set('ticker', ticker);
    params.set('type', analysisType);
    params.set('provider', provider);
    params.set('period', period);
    
    router.push(`/analysis?${params.toString()}`);
  }, [ticker, analysisType, provider, period, router]);
  
  // Handler for form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTicker(inputTicker.toUpperCase());
  };
  
  return (
    <DashboardLayout>
      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 gap-6">
          <div className="card p-6">
            <div className="mb-4">
              <h2 className="text-2xl font-bold">AI-Powered Stock Analysis</h2>
              <p className="text-gray-600">
                Generate detailed stock analysis using advanced AI models
              </p>
            </div>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
                <div className="space-y-2">
                  <label htmlFor="ticker" className="block text-sm font-medium">Stock Symbol</label>
                  <div className="flex gap-2">
                    <input
                      id="ticker"
                      value={inputTicker}
                      onChange={(e) => setInputTicker(e.target.value.toUpperCase())}
                      placeholder="AAPL"
                      className="input w-full"
                    />
                    <button type="submit" className="button-primary">Analyze</button>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <label htmlFor="analysis-type" className="block text-sm font-medium">Analysis Type</label>
                  <select 
                    id="analysis-type"
                    className="input w-full"
                    value={analysisType} 
                    onChange={(e) => setAnalysisType(e.target.value as AnalysisType)}
                  >
                    <option value="technical">Technical Analysis</option>
                    <option value="comprehensive">Comprehensive Analysis</option>
                  </select>
                </div>
                
                <div className="space-y-2">
                  <label htmlFor="provider" className="block text-sm font-medium">AI Provider</label>
                  <select 
                    id="provider"
                    className="input w-full"
                    value={provider} 
                    onChange={(e) => setProvider(e.target.value as AnalysisProvider)}
                  >
                    <option value="openai">OpenAI (GPT-4)</option>
                    <option value="gemini">Google Gemini</option>
                  </select>
                </div>
                
                <div className="space-y-2">
                  <label htmlFor="period" className="block text-sm font-medium">Time Period</label>
                  <select 
                    id="period"
                    className="input w-full"
                    value={period} 
                    onChange={(e) => setPeriod(e.target.value)}
                  >
                    <option value="1D">1 Day</option>
                    <option value="5D">5 Days</option>
                    <option value="1M">1 Month</option>
                    <option value="3M">3 Months</option>
                    <option value="6M">6 Months</option>
                    <option value="1Y">1 Year</option>
                    <option value="5Y">5 Years</option>
                  </select>
                </div>
              </div>
            </form>
          </div>
          
          {ticker && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="card p-6 col-span-1 md:col-span-2">
                <div className="mb-4">
                  <h2 className="text-xl font-semibold">{ticker}</h2>
                  <p className="text-gray-600">Stock Price History</p>
                </div>
                <TimeSeriesChart 
                  data={timeSeriesData}
                  isLoading={isTimeSeriesLoading}
                  showVolume={true}
                  symbol={ticker}
                  period={period}
                />
              </div>
              
              <div className="card p-6 col-span-1">
                <div className="mb-4">
                  <h2 className="text-xl font-semibold">Market Overview</h2>
                  <p className="text-gray-600">Current market data for {ticker}</p>
                </div>
                <div className="space-y-4">
                  {marketData ? (
                    <>
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">Price</span>
                        <span className="font-bold">${marketData.regularMarketPrice.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">Change</span>
                        <span className={`font-bold ${marketData.regularMarketChangePercent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {marketData.regularMarketChangePercent >= 0 ? '+' : ''}{marketData.regularMarketChangePercent.toFixed(2)}%
                        </span>
                      </div>
                      <hr className="border-gray-200" />
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">Open</span>
                        <span className="font-medium">${marketData.regularMarketOpen.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">High</span>
                        <span className="font-medium">${marketData.regularMarketDayHigh.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">Low</span>
                        <span className="font-medium">${marketData.regularMarketDayLow.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">Volume</span>
                        <span className="font-medium">{(marketData.regularMarketVolume/1000000).toFixed(2)}M</span>
                      </div>
                      <hr className="border-gray-200" />
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">Market Cap</span>
                        <span className="font-medium">${(marketData.marketCap/1000000000).toFixed(2)}B</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">P/E Ratio</span>
                        <span className="font-medium">{marketData.trailingPE?.toFixed(2) || 'N/A'}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">Div Yield</span>
                        <span className="font-medium">{marketData.dividendYield ? (marketData.dividendYield * 100).toFixed(2) + '%' : 'N/A'}</span>
                      </div>
                    </>
                  ) : (
                    <div className="text-center py-4">Loading market data...</div>
                  )}
                </div>
              </div>
            </div>
          )}
          
          <div className="mt-6">
            {analysisType === 'technical' ? (
              <TechnicalAnalysisCard
                ticker={ticker}
                analysis={analysis}
                provider={provider}
                isLoading={isAnalysisLoading}
                error={analysisError}
              />
            ) : (
              <ComprehensiveAnalysisCard
                ticker={ticker}
                analysis={analysis}
                provider={provider}
                isLoading={isAnalysisLoading}
                error={analysisError}
              />
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
} 