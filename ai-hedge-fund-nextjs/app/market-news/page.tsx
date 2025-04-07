'use client';

import { useState } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import NewsList from '@/components/news/NewsList';
import TrendingStocks from '@/components/trends/TrendingStocks';
import { useNews } from '@/hooks/useNews';
import { useMarketTrends } from '@/hooks/useMarketTrends';

export default function MarketNewsPage() {
  const [ticker, setTicker] = useState('');
  
  // Fetch market news
  const { 
    data: newsData, 
    isLoading: isLoadingNews, 
    isError: isErrorNews 
  } = useNews(ticker);
  
  // Fetch market trends
  const { 
    data: trendsData, 
    isLoading: isLoadingTrends, 
    isError: isErrorTrends 
  } = useMarketTrends('all');
  
  // Handler for ticker input change
  const handleTickerChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTicker(e.target.value.toUpperCase());
  };
  
  // Clear ticker to show general market news
  const handleClearTicker = () => {
    setTicker('');
  };
  
  return (
    <DashboardLayout>
      <div className="space-y-8">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <h1>Market News</h1>
          
          <div className="flex items-center space-x-2">
            <input
              type="text"
              placeholder="Filter by ticker (e.g., AAPL)"
              value={ticker}
              onChange={handleTickerChange}
              className="input"
            />
            
            {ticker && (
              <button 
                onClick={handleClearTicker}
                className="btn-secondary"
              >
                Show All News
              </button>
            )}
          </div>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* News Section - Takes up 2/3 on larger screens */}
          <div className="lg:col-span-2">
            <NewsList
              articles={newsData?.news || []}
              title={ticker ? `${ticker} News` : 'Market News'}
              isLoading={isLoadingNews}
              isEmpty={!isLoadingNews && (!newsData?.news || newsData.news.length === 0)}
            />
            
            {isErrorNews && (
              <div className="mt-4 bg-danger-50 border border-danger-200 text-danger-700 p-4 rounded-md">
                <p className="font-medium">Error loading news data</p>
                <p className="text-sm mt-1">Please try again later.</p>
              </div>
            )}
          </div>
          
          {/* Trending Stocks Section - Takes up 1/3 on larger screens */}
          <div>
            <h2 className="text-xl font-semibold mb-4">Trending Stocks</h2>
            
            <TrendingStocks
              gainers={'gainers' in trendsData ? trendsData.gainers : []}
              losers={'losers' in trendsData ? trendsData.losers : []}
              isLoading={isLoadingTrends}
            />
            
            {isErrorTrends && (
              <div className="mt-4 bg-danger-50 border border-danger-200 text-danger-700 p-4 rounded-md">
                <p className="font-medium">Error loading trends data</p>
                <p className="text-sm mt-1">Please try again later.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
} 