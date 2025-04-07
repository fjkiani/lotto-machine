'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import TimeSeriesChart from '@/components/charts/TimeSeriesChart';
import TechnicalAnalysisCard from '@/components/analysis/TechnicalAnalysisCard';
import ComprehensiveAnalysisCard from '@/components/analysis/ComprehensiveAnalysisCard';
import NewsList from '@/components/news/NewsList';
import { useMarketData } from '@/hooks/useMarketData';
import { useStockInsights } from '@/hooks/useStockInsights';
import { useNews } from '@/hooks/useNews';
import { useTimeSeries } from '@/hooks/useTimeSeries';
import { useAnalysis, AnalysisType, ProviderType } from '@/hooks/useAnalysis';

// Define the available analysis types and providers as constants
// This makes it easy to add new options in the future
const ANALYSIS_TYPES: { id: AnalysisType; label: string }[] = [
  { id: 'technical', label: 'Technical Analysis' },
  { id: 'comprehensive', label: 'Comprehensive Analysis' },
];

const LLM_PROVIDERS: { id: ProviderType; label: string }[] = [
  { id: 'openai', label: 'OpenAI' },
  { id: 'gemini', label: 'Google Gemini' },
];

// Time periods for analysis - can be expanded in the future
const TIME_PERIODS = [
  { id: '1D', label: '1 Day' },
  { id: '5D', label: '5 Days' },
  { id: '1M', label: '1 Month' },
  { id: '3M', label: '3 Months' },
  { id: '6M', label: '6 Months' },
  { id: '1Y', label: '1 Year' },
];

export default function AIAnalysisPage() {
  // Get search params and router for URL-based state
  const searchParams = useSearchParams();
  const router = useRouter();
  
  // Initialize state from URL or defaults
  const [ticker, setTicker] = useState(
    searchParams.get('ticker') || process.env.NEXT_PUBLIC_DEFAULT_TICKER || 'AAPL'
  );
  const [analysisType, setAnalysisType] = useState<AnalysisType>(
    (searchParams.get('type') as AnalysisType) || 'technical'
  );
  const [provider, setProvider] = useState<ProviderType>(
    (searchParams.get('provider') as ProviderType) || 'openai'
  );
  const [period, setPeriod] = useState(
    searchParams.get('period') || '1M'
  );
  
  // Fetch all necessary data
  const { data: marketData, isLoading: isLoadingMarket } = useMarketData(ticker);
  const { data: insights, isLoading: isLoadingInsights } = useStockInsights(ticker);
  const { data: timeSeriesData, isLoading: isLoadingTimeSeries } = useTimeSeries(ticker, period as any);
  const { data: newsData, isLoading: isLoadingNews } = useNews(ticker);
  
  // Fetch analysis - only fetch if marketData and insights are available
  const shouldFetchAnalysis = !!marketData && !!insights;
  const { 
    data: analysisData, 
    isLoading: isLoadingAnalysis,
    isError: isErrorAnalysis,
    mutate: refreshAnalysis 
  } = useAnalysis(
    shouldFetchAnalysis ? ticker : '',
    analysisType,
    provider,
    period
  );
  
  // Update URL when parameters change
  useEffect(() => {
    const params = new URLSearchParams();
    params.set('ticker', ticker);
    params.set('type', analysisType);
    params.set('provider', provider);
    params.set('period', period);
    
    router.push(`/ai-analysis?${params.toString()}`, { scroll: false });
  }, [ticker, analysisType, provider, period, router]);
  
  // Handle form changes
  const handleTickerChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTicker(e.target.value.toUpperCase());
  };
  
  const handleAnalysisTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setAnalysisType(e.target.value as AnalysisType);
  };
  
  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setProvider(e.target.value as ProviderType);
  };
  
  const handlePeriodChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setPeriod(e.target.value);
  };
  
  // Handle analysis refresh
  const handleRefreshAnalysis = () => {
    refreshAnalysis();
  };
  
  // Determine if we're still loading initial data
  const isLoading = isLoadingMarket || isLoadingInsights || 
                   isLoadingTimeSeries || isLoadingAnalysis;
  
  // Handle errors
  const hasError = isErrorAnalysis;
  
  return (
    <DashboardLayout>
      <div className="space-y-8">
        <div>
          <h1 className="mb-4">AI-Powered Market Analysis</h1>
          
          {/* Analysis Configuration Form */}
          <div className="card mb-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              {/* Ticker Input */}
              <div>
                <label htmlFor="ticker" className="block text-sm font-medium mb-1">
                  Stock Symbol
                </label>
                <input
                  id="ticker"
                  type="text"
                  value={ticker}
                  onChange={handleTickerChange}
                  className="input w-full"
                  placeholder="e.g., AAPL"
                />
              </div>
              
              {/* Analysis Type Select */}
              <div>
                <label htmlFor="analysisType" className="block text-sm font-medium mb-1">
                  Analysis Type
                </label>
                <select
                  id="analysisType"
                  value={analysisType}
                  onChange={handleAnalysisTypeChange}
                  className="input w-full"
                >
                  {ANALYSIS_TYPES.map(type => (
                    <option key={type.id} value={type.id}>{type.label}</option>
                  ))}
                </select>
              </div>
              
              {/* Provider Select */}
              <div>
                <label htmlFor="provider" className="block text-sm font-medium mb-1">
                  LLM Provider
                </label>
                <select
                  id="provider"
                  value={provider}
                  onChange={handleProviderChange}
                  className="input w-full"
                >
                  {LLM_PROVIDERS.map(providerOption => (
                    <option key={providerOption.id} value={providerOption.id}>{providerOption.label}</option>
                  ))}
                </select>
              </div>
              
              {/* Time Period Select */}
              <div>
                <label htmlFor="period" className="block text-sm font-medium mb-1">
                  Time Period
                </label>
                <select
                  id="period"
                  value={period}
                  onChange={handlePeriodChange}
                  className="input w-full"
                >
                  {TIME_PERIODS.map(timeOption => (
                    <option key={timeOption.id} value={timeOption.id}>{timeOption.label}</option>
                  ))}
                </select>
              </div>
              
              {/* Refresh Button */}
              <div className="flex items-end">
                <button
                  onClick={handleRefreshAnalysis}
                  disabled={isLoading || !shouldFetchAnalysis}
                  className="button-primary w-full"
                >
                  {isLoadingAnalysis ? 'Loading...' : 'Generate Analysis'}
                </button>
              </div>
            </div>
          </div>
        </div>
        
        {/* Loading State */}
        {isLoading && (
          <div className="flex justify-center py-12">
            <div className="text-center">
              <div className="text-xl mb-2">Generating AI Analysis...</div>
              <div className="text-gray-500">This may take a moment</div>
            </div>
          </div>
        )}
        
        {/* Error State */}
        {hasError && !isLoading && (
          <div className="bg-danger-50 border border-danger-200 text-danger-700 p-6 rounded-md">
            <h2 className="text-xl font-semibold mb-2">Error Generating Analysis</h2>
            <p>We couldn't generate the analysis at this time. Please try again later or select different parameters.</p>
          </div>
        )}
        
        {/* Analysis Results */}
        {!isLoading && !hasError && analysisData && (
          <div className="space-y-8">
            {/* Price Chart */}
            {timeSeriesData && (
              <div className="card p-6">
                <h2 className="text-xl font-semibold mb-4">{ticker} Price Chart</h2>
                <TimeSeriesChart
                  data={timeSeriesData.time_series}
                  symbol={ticker}
                  name={timeSeriesData.name}
                  price={timeSeriesData.price}
                  change={timeSeriesData.change}
                  changePercent={timeSeriesData.change_percent}
                  period={period}
                  height={400}
                  showVolume={true}
                />
              </div>
            )}
            
            {/* Analysis Results */}
            <div className="card p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold">
                  {analysisType === 'technical' ? 'Technical Analysis' : 'Comprehensive Analysis'}
                </h2>
                <div className="text-sm text-gray-500">
                  Generated by {provider === 'openai' ? 'OpenAI' : 'Google Gemini'} at{' '}
                  {new Date(analysisData.timestamp).toLocaleString()}
                </div>
              </div>
              
              {analysisData.analysis_type === 'technical' && (
                <TechnicalAnalysisCard
                  analysis={analysisData.result}
                  ticker={ticker}
                  currentPrice={marketData?.regularMarketPrice}
                />
              )}
              
              {analysisData.analysis_type === 'comprehensive' && (
                <ComprehensiveAnalysisCard
                  analysis={analysisData.result}
                  ticker={ticker}
                  currentPrice={marketData?.regularMarketPrice}
                />
              )}
            </div>
            
            {/* Related News */}
            {newsData && newsData.news && (
              <div className="card p-6">
                <NewsList
                  articles={newsData.news}
                  title={`Latest ${ticker} News`}
                  isLoading={isLoadingNews}
                  isEmpty={!isLoadingNews && (!newsData.news || newsData.news.length === 0)}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
} 