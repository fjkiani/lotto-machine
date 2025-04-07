'use client';

import { useState } from 'react';
import Link from 'next/link';
import DashboardLayout from '@/components/layout/DashboardLayout';
import MetricCard from '@/components/cards/MetricCard';
import NewsList from '@/components/news/NewsList';
import TrendingStocks from '@/components/trends/TrendingStocks';
import { useMarketData } from '@/hooks/useMarketData';
import { useNews } from '@/hooks/useNews';
import { useMarketTrends } from '@/hooks/useMarketTrends';

export default function DashboardPage() {
  const [ticker, setTicker] = useState(process.env.NEXT_PUBLIC_DEFAULT_TICKER || 'AAPL');
  
  // Fetch market data for the current ticker
  const { data: marketData, isLoading: isLoadingMarket } = useMarketData(ticker);
  
  // Fetch market news (not ticker-specific)
  const { data: newsData, isLoading: isLoadingNews } = useNews();
  
  // Fetch market trends (gainers and losers)
  const { data: trendsData, isLoading: isLoadingTrends } = useMarketTrends('all');
  
  // Handler for ticker input change
  const handleTickerChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTicker(e.target.value.toUpperCase());
  };
  
  // Format values for display
  const formatCurrency = (value: string | number) => {
    const numValue = typeof value === 'string' ? parseFloat(value) : value;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(numValue);
  };
  
  const formatVolume = (value: string | number) => {
    const numValue = typeof value === 'string' ? parseFloat(value) : value;
    if (numValue >= 1_000_000_000) {
      return `${(numValue / 1_000_000_000).toFixed(2)}B`;
    } else if (numValue >= 1_000_000) {
      return `${(numValue / 1_000_000).toFixed(2)}M`;
    } else if (numValue >= 1_000) {
      return `${(numValue / 1_000).toFixed(2)}K`;
    }
    return numValue.toString();
  };
  
  const formatMarketCap = (value: string | number) => {
    const numValue = typeof value === 'string' ? parseFloat(value) : value;
    if (numValue >= 1_000_000_000_000) {
      return `$${(numValue / 1_000_000_000_000).toFixed(2)}T`;
    } else if (numValue >= 1_000_000_000) {
      return `$${(numValue / 1_000_000_000).toFixed(2)}B`;
    } else if (numValue >= 1_000_000) {
      return `$${(numValue / 1_000_000).toFixed(2)}M`;
    }
    return formatCurrency(numValue);
  };
  
  // Extract gainers and losers from trendsData with proper null checks
  const gainers = trendsData && 'gainers' in trendsData ? trendsData.gainers.slice(0, 5) : [];
  const losers = trendsData && 'losers' in trendsData ? trendsData.losers.slice(0, 5) : [];
  
  return (
    <DashboardLayout>
      <div className="space-y-8">
        <div className="flex justify-between items-center">
          <h1>Dashboard</h1>
          
          <div className="flex items-center space-x-2">
            <label htmlFor="ticker" className="text-sm font-medium">
              Stock Symbol:
            </label>
            <input
              id="ticker"
              type="text"
              value={ticker}
              onChange={handleTickerChange}
              className="input w-28"
              placeholder="e.g. AAPL"
            />
          </div>
        </div>
        
        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {isLoadingMarket ? (
            <div className="col-span-3 h-24 flex justify-center items-center">
              <p>Loading market data...</p>
            </div>
          ) : marketData ? (
            <>
              <MetricCard
                title="Current Price"
                value={marketData.regularMarketPrice}
                change={marketData.regularMarketChangePercent}
                changePercent={marketData.regularMarketChangePercent}
                formatter={formatCurrency}
              />
              <MetricCard
                title="Volume"
                value={marketData.regularMarketVolume}
                formatter={formatVolume}
              />
              <MetricCard
                title="Market Cap"
                value={marketData.marketCap}
                formatter={formatMarketCap}
              />
            </>
          ) : (
            <div className="col-span-3 h-24 flex justify-center items-center">
              <p>No market data available.</p>
            </div>
          )}
        </div>
        
        {/* Analysis Links */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Analysis</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Link href={`/market-overview?ticker=${ticker}`} className="card p-6 hover:shadow-md transition-shadow">
              <h3 className="text-lg font-medium mb-2">Market Overview</h3>
              <p className="text-gray-500">Comprehensive overview of {ticker} market data, including key statistics and price information.</p>
            </Link>
            
            <Link href={`/technical-analysis?ticker=${ticker}`} className="card p-6 hover:shadow-md transition-shadow">
              <h3 className="text-lg font-medium mb-2">Technical Analysis</h3>
              <p className="text-gray-500">Technical indicators, support/resistance levels, and analyst recommendations.</p>
            </Link>
            
            <Link href={`/options-analysis?ticker=${ticker}`} className="card p-6 hover:shadow-md transition-shadow">
              <h3 className="text-lg font-medium mb-2">Options Analysis</h3>
              <p className="text-gray-500">Options chain visualization, implied volatility, and key options metrics.</p>
            </Link>
            
            <Link href={`/memory-analysis?ticker=${ticker}`} className="card p-6 hover:shadow-md transition-shadow">
              <h3 className="text-lg font-medium mb-2">Memory Analysis</h3>
              <p className="text-gray-500">AI-powered analysis with historical context for better investment decisions.</p>
            </Link>
          </div>
        </div>
        
        {/* Market News and Trends Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Market News */}
          <div className="lg:col-span-2">
            <h2 className="text-xl font-semibold mb-4">Latest Market News</h2>
            <NewsList
              articles={newsData?.news?.slice(0, 6) || []}
              isLoading={isLoadingNews}
              isEmpty={!isLoadingNews && (!newsData?.news || newsData.news.length === 0)}
              title=""
            />
            
            <div className="mt-4 text-center">
              <Link href="/market-news" className="btn-primary">
                View All Market News
              </Link>
            </div>
          </div>
          
          {/* Trending Stocks */}
          <div>
            <h2 className="text-xl font-semibold mb-4">Trending Stocks</h2>
            <TrendingStocks
              gainers={gainers}
              losers={losers}
              isLoading={isLoadingTrends}
            />
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
} 