'use client';

import { useState } from 'react';
import { OptionsChain, OptionStraddle } from '@/lib/connectors/options-chain';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

interface OptionsChainTableProps {
  data: OptionsChain | null;
  isLoading: boolean;
  error: string | null;
  onExpirationChange?: (expiration: string) => void;
}

export function OptionsChainTable({
  data,
  isLoading,
  error,
  onExpirationChange
}: OptionsChainTableProps) {
  const [selectedTab, setSelectedTab] = useState<string>('calls');

  // Handler for expiration date change
  const handleExpirationChange = (date: string) => {
    if (onExpirationChange) {
      onExpirationChange(date);
    }
  };

  // Function to format price
  const formatPrice = (price: number) => {
    return price ? `$${price.toFixed(2)}` : '-';
  };

  // Function to format number with commas for thousands
  const formatNumber = (num: number) => {
    return num ? num.toLocaleString() : '-';
  };

  // Function to format implied volatility as percentage
  const formatIV = (iv: number) => {
    return iv ? `${(iv * 100).toFixed(2)}%` : '-';
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Options Chain</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Options Chain</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="p-4 bg-red-50 text-red-600 rounded-md">
            Error: {error}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Options Chain</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="p-4 bg-gray-50 text-gray-600 rounded-md">
            No options data available. Please enter a ticker symbol.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex justify-between items-center">
          <span>Options Chain: {data.symbol}</span>
          <Badge>
            Current Price: ${data.currentPrice.toFixed(2)}
          </Badge>
        </CardTitle>
      </CardHeader>

      <CardContent>
        {/* Expiration Date Selector */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Expiration Date
          </label>
          <div className="flex flex-wrap gap-2">
            {data.expirationDates.map((expDate) => (
              <Badge
                key={expDate.date}
                variant="outline"
                className="cursor-pointer hover:bg-gray-100"
                onClick={() => handleExpirationChange(expDate.date)}
              >
                {expDate.date}
              </Badge>
            ))}
          </div>
        </div>

        {/* Calls/Puts Tabs */}
        <Tabs
          value={selectedTab}
          onValueChange={setSelectedTab}
          className="w-full"
        >
          <TabsList className="w-full">
            <TabsTrigger value="calls" className="w-1/2">
              Calls
            </TabsTrigger>
            <TabsTrigger value="puts" className="w-1/2">
              Puts
            </TabsTrigger>
          </TabsList>

          {/* Calls Table */}
          <TabsContent value="calls">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                  <tr>
                    <th className="px-3 py-2">Strike</th>
                    <th className="px-3 py-2">Bid</th>
                    <th className="px-3 py-2">Ask</th>
                    <th className="px-3 py-2">IV</th>
                    <th className="px-3 py-2">Volume</th>
                    <th className="px-3 py-2">Open Int</th>
                    <th className="px-3 py-2">ITM</th>
                  </tr>
                </thead>
                <tbody>
                  {data.straddles
                    .filter((straddle) => straddle.call !== null)
                    .map((straddle) => (
                      <tr 
                        key={`call-${straddle.strike}`}
                        className={`border-b hover:bg-gray-50 ${
                          straddle.strike === data.currentPrice 
                            ? 'bg-blue-50' 
                            : ''
                        }`}
                      >
                        <td className="px-3 py-2 font-medium">${straddle.strike.toFixed(2)}</td>
                        <td className="px-3 py-2">{formatPrice(straddle.call?.bid || 0)}</td>
                        <td className="px-3 py-2">{formatPrice(straddle.call?.ask || 0)}</td>
                        <td className="px-3 py-2">{formatIV(straddle.call?.impliedVolatility || 0)}</td>
                        <td className="px-3 py-2">{formatNumber(straddle.call?.volume || 0)}</td>
                        <td className="px-3 py-2">{formatNumber(straddle.call?.openInterest || 0)}</td>
                        <td className="px-3 py-2">
                          {straddle.call?.inTheMoney ? (
                            <Badge variant="default" className="bg-green-500">Yes</Badge>
                          ) : (
                            <Badge variant="outline">No</Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </TabsContent>

          {/* Puts Table */}
          <TabsContent value="puts">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                  <tr>
                    <th className="px-3 py-2">Strike</th>
                    <th className="px-3 py-2">Bid</th>
                    <th className="px-3 py-2">Ask</th>
                    <th className="px-3 py-2">IV</th>
                    <th className="px-3 py-2">Volume</th>
                    <th className="px-3 py-2">Open Int</th>
                    <th className="px-3 py-2">ITM</th>
                  </tr>
                </thead>
                <tbody>
                  {data.straddles
                    .filter((straddle) => straddle.put !== null)
                    .map((straddle) => (
                      <tr 
                        key={`put-${straddle.strike}`}
                        className={`border-b hover:bg-gray-50 ${
                          straddle.strike === data.currentPrice 
                            ? 'bg-blue-50' 
                            : ''
                        }`}
                      >
                        <td className="px-3 py-2 font-medium">${straddle.strike.toFixed(2)}</td>
                        <td className="px-3 py-2">{formatPrice(straddle.put?.bid || 0)}</td>
                        <td className="px-3 py-2">{formatPrice(straddle.put?.ask || 0)}</td>
                        <td className="px-3 py-2">{formatIV(straddle.put?.impliedVolatility || 0)}</td>
                        <td className="px-3 py-2">{formatNumber(straddle.put?.volume || 0)}</td>
                        <td className="px-3 py-2">{formatNumber(straddle.put?.openInterest || 0)}</td>
                        <td className="px-3 py-2">
                          {straddle.put?.inTheMoney ? (
                            <Badge variant="default" className="bg-red-500">Yes</Badge>
                          ) : (
                            <Badge variant="outline">No</Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
} 