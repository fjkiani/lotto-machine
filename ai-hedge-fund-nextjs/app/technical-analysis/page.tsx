'use client';

import { useState } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import TechnicalSignals from '@/components/technical/TechnicalSignals';
import TechnicalLevels from '@/components/technical/TechnicalLevels';
import AnalystRecommendations from '@/components/technical/AnalystRecommendations';
import NewsList from '@/components/news/NewsList';
import TimeSeriesChart from '@/components/charts/TimeSeriesChart';
import { useMarketData } from '@/hooks/useMarketData';
import { useStockInsights } from '@/hooks/useStockInsights';
import { useNews } from '@/hooks/useNews';
import { useTimeSeries } from '@/hooks/useTimeSeries';

export default function TechnicalAnalysisPage() {
  const [ticker, setTicker] = useState(process.env.NEXT_PUBLIC_DEFAULT_TICKER || 'AAPL');
  const [period, setPeriod] = useState('1M');
  
  // Fetch market data, technical insights, news, and time series data
  const { data: marketData, isLoading: isLoadingMarket, isError: isErrorMarket } = useMarketData(ticker);
  const { data: insights, isLoading: isLoadingInsights, isError: isErrorInsights } = useStockInsights(ticker);
  const { data: newsData, isLoading: isLoadingNews, isError: isErrorNews } = useNews(ticker);
  const { data: timeSeriesData, isLoading: isLoadingTimeSeries, isError: isErrorTimeSeries } = useTimeSeries(ticker, period as any);
  
  const handleTickerChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTicker(e.target.value.toUpperCase());
  };
  
  const handlePeriodChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setPeriod(e.target.value);
  };
  
  // Determine if we're in a loading state
  const isLoading = isLoadingMarket || isLoadingInsights || isLoadingNews || isLoadingTimeSeries;
  
  // Determine if we have any errors
  const isError = isErrorMarket || isErrorInsights || isErrorNews || isErrorTimeSeries;
  
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1>Technical Analysis</h1>
          
          <div className="flex items-center space-x-4">
            <label htmlFor="ticker" className="text-sm font-medium">
              Stock Symbol:
            </label>
            <input
              id="ticker"
              type="text"
              value={ticker}
              onChange={handleTickerChange}
              className="input w-28 uppercase"
              placeholder="e.g. AAPL"
            />
            
            <label htmlFor="period" className="text-sm font-medium">
              Time Period:
            </label>
            <select
              id="period"
              value={period}
              onChange={handlePeriodChange}
              className="input w-24"
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
        
        {isLoading && (
          <div className="flex justify-center items-center h-64">
            <p className="text-lg">Loading technical analysis data...</p>
          </div>
        )}
        
        {isError && (
          <div className="bg-danger-50 border border-danger-200 text-danger-700 p-4 rounded-md">
            <p className="font-medium">Error loading technical data</p>
            <p className="text-sm mt-1">Please check the ticker symbol and try again.</p>
          </div>
        )}
        
        {!isLoading && !isError && insights && marketData && (
          <>
            {/* Historical Price Chart */}
            {timeSeriesData && timeSeriesData.time_series && (
              <section className="mt-8">
                <h2 className="text-xl font-semibold mb-4">Historical Price Data</h2>
                <TimeSeriesChart 
                  data={timeSeriesData.time_series}
                  symbol={ticker}
                  name={timeSeriesData.name}
                  price={timeSeriesData.price}
                  change={timeSeriesData.change}
                  changePercent={timeSeriesData.change_percent}
                  period={period}
                  height={400}
                  width={800}
                />
              </section>
            )}
            
            {/* Technical Signals Section */}
            <section>
              <h2 className="text-xl font-semibold mb-4">Technical Signals</h2>
              <TechnicalSignals signals={insights.technicalEvents} />
            </section>
            
            {/* Technical Levels Section */}
            <section className="mt-8">
              <h2 className="text-xl font-semibold mb-4">Technical Levels</h2>
              <div className="flex justify-center">
                <TechnicalLevels 
                  levels={insights.keyTechnicals} 
                  currentPrice={marketData.regularMarketPrice}
                />
              </div>
            </section>
            
            {/* Valuation Section */}
            {insights.valuation && insights.valuation.description && (
              <section className="mt-8">
                <h2 className="text-xl font-semibold mb-4">Valuation</h2>
                <div className="card">
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="text-xl font-medium">{insights.valuation.description}</p>
                      <p className="text-sm text-gray-500 mt-1">Provider: {insights.valuation.provider}</p>
                    </div>
                  </div>
                </div>
              </section>
            )}
            
            {/* Analyst Recommendations Section */}
            <section className="mt-8">
              <h2 className="text-xl font-semibold mb-4">Analyst Recommendations</h2>
              <AnalystRecommendations 
                recommendation={insights.recommendation} 
                reports={[]}
              />
            </section>
            
            {/* Stock News Section */}
            <section className="mt-8">
              <NewsList
                articles={newsData?.news || []}
                title={`Latest ${ticker} News`}
                isLoading={isLoadingNews}
                isEmpty={!isLoadingNews && (!newsData?.news || newsData.news.length === 0)}
              />
              
              {isErrorNews && (
                <div className="mt-4 bg-danger-50 border border-danger-200 text-danger-700 p-4 rounded-md">
                  <p className="font-medium">Error loading news data</p>
                  <p className="text-sm mt-1">Please try again later.</p>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </DashboardLayout>
  );
} 