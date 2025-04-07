'use client';

import { useState } from 'react';
import { TrendItem } from '@/lib/connectors/real-time-finance';
import Link from 'next/link';

interface TrendingStocksProps {
  gainers?: TrendItem[];
  losers?: TrendItem[];
  isLoading?: boolean;
}

export default function TrendingStocks({ 
  gainers = [], 
  losers = [],
  isLoading = false
}: TrendingStocksProps) {
  const [activeTab, setActiveTab] = useState<'gainers' | 'losers'>('gainers');
  
  // Helper function to format percentage changes
  const formatPercentage = (value: number) => {
    if (value === undefined || value === null) return 'N/A';
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };
  
  // Helper function to format prices
  const formatPrice = (value: number, currency: string = 'USD') => {
    if (value === undefined || value === null) return 'N/A';
    return new Intl.NumberFormat('en-US', { 
      style: 'currency', 
      currency: currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  };
  
  // Get active trends based on selected tab
  const activeTrends = activeTab === 'gainers' ? gainers : losers;
  
  return (
    <div className="card">
      <div className="flex border-b border-gray-200 dark:border-gray-700">
        <button
          className={`px-4 py-2 font-medium text-sm ${
            activeTab === 'gainers' 
              ? 'border-b-2 border-primary-500 text-primary-600' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => setActiveTab('gainers')}
        >
          Top Gainers
        </button>
        <button
          className={`px-4 py-2 font-medium text-sm ${
            activeTab === 'losers' 
              ? 'border-b-2 border-primary-500 text-primary-600' 
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => setActiveTab('losers')}
        >
          Top Losers
        </button>
      </div>
      
      <div className="py-4">
        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <p>Loading trending stocks...</p>
          </div>
        ) : activeTrends.length === 0 ? (
          <div className="p-4 text-center">
            <p className="text-gray-500">No data available.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-800">
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Symbol
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Price
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Change %
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {activeTrends.slice(0, 10).map((trend, index) => {
                  // Extract just the symbol without exchange suffix
                  const symbolOnly = trend.symbol.includes(':') 
                    ? trend.symbol.split(':')[0] 
                    : trend.symbol;
                  
                  // Determine color for change percentage
                  const changeColorClass = trend.change_percent > 0 
                    ? 'text-success-600' 
                    : 'text-danger-600';
                  
                  return (
                    <tr key={`${trend.symbol}-${index}`} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="px-4 py-3 whitespace-nowrap font-medium">
                        <Link
                          href={`/technical-analysis?ticker=${symbolOnly}`}
                          className="text-primary-600 hover:text-primary-800"
                        >
                          {symbolOnly}
                        </Link>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap truncate max-w-[200px]">
                        {trend.name}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-right">
                        {formatPrice(trend.price, trend.currency)}
                      </td>
                      <td className={`px-4 py-3 whitespace-nowrap text-right ${changeColorClass} font-medium`}>
                        {formatPercentage(trend.change_percent)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
} 