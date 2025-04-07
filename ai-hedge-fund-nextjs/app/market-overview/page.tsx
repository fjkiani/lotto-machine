'use client';

import { useState } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import MetricCard from '@/components/cards/MetricCard';
import { useMarketData } from '@/hooks/useMarketData';

// Formatter functions
const formatCurrency = (value: string | number) => {
  return `$${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatPercent = (value: string | number) => {
  return `${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
};

const formatVolume = (value: string | number) => {
  const num = Number(value);
  if (num >= 1_000_000_000) {
    return `${(num / 1_000_000_000).toFixed(2)}B`;
  } else if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(2)}M`;
  } else if (num >= 1_000) {
    return `${(num / 1_000).toFixed(2)}K`;
  }
  return num.toLocaleString();
};

const formatMarketCap = (value: string | number) => {
  const num = Number(value);
  if (num >= 1_000_000_000_000) {
    return `$${(num / 1_000_000_000_000).toFixed(2)}T`;
  } else if (num >= 1_000_000_000) {
    return `$${(num / 1_000_000_000).toFixed(2)}B`;
  } else if (num >= 1_000_000) {
    return `$${(num / 1_000_000).toFixed(2)}M`;
  }
  return `$${num.toLocaleString()}`;
};

export default function MarketOverviewPage() {
  const [ticker, setTicker] = useState(process.env.NEXT_PUBLIC_DEFAULT_TICKER || 'AAPL');
  const { data: marketData, isLoading, isError } = useMarketData(ticker);
  
  const handleTickerChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTicker(e.target.value.toUpperCase());
  };
  
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1>Market Overview</h1>
          
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
          </div>
        </div>
        
        {isLoading && (
          <div className="flex justify-center items-center h-64">
            <p className="text-lg">Loading market data...</p>
          </div>
        )}
        
        {isError && (
          <div className="bg-danger-50 border border-danger-200 text-danger-700 p-4 rounded-md">
            <p className="font-medium">Error loading market data</p>
            <p className="text-sm mt-1">Please check the ticker symbol and try again.</p>
          </div>
        )}
        
        {!isLoading && !isError && marketData && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <MetricCard
                title="Current Price"
                value={marketData.regularMarketPrice}
                change={marketData.regularMarketChangePercent}
                isPositive={marketData.regularMarketChangePercent > 0}
                isNegative={marketData.regularMarketChangePercent < 0}
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
            </div>
            
            <div className="mt-8">
              <h2>Additional Market Information</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-4">
                <MetricCard
                  title="Day Range"
                  value={`${formatCurrency(marketData.regularMarketDayLow)} - ${formatCurrency(marketData.regularMarketDayHigh)}`}
                />
                
                <MetricCard
                  title="Open"
                  value={marketData.regularMarketOpen}
                  formatter={formatCurrency}
                />
                
                <MetricCard
                  title="Previous Close"
                  value={marketData.regularMarketPreviousClose}
                  formatter={formatCurrency}
                />
                
                <MetricCard
                  title="Avg. Daily Volume (10D)"
                  value={marketData.averageDailyVolume10Day}
                  formatter={formatVolume}
                />
                
                <MetricCard
                  title="52 Week Low"
                  value={marketData.fiftyTwoWeekLow}
                  formatter={formatCurrency}
                />
                
                <MetricCard
                  title="52 Week High"
                  value={marketData.fiftyTwoWeekHigh}
                  formatter={formatCurrency}
                />
                
                <MetricCard
                  title="P/E Ratio"
                  value={marketData.trailingPE || 'N/A'}
                  formatter={(value) => value === 'N/A' ? 'N/A' : Number(value).toFixed(2)}
                />
                
                <MetricCard
                  title="Dividend Yield"
                  value={marketData.dividendYield || 0}
                  formatter={formatPercent}
                />
              </div>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
} 