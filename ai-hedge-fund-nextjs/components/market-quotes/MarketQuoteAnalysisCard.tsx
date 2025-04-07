'use client';

import React from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '@/components/ui/card';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger
} from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowUpCircle, ArrowDownCircle, MinusCircle, Clock, Target, Zap } from 'lucide-react';
import { MarketQuoteAnalysis } from '@/lib/connectors/market-quotes';
import { formatTimestamp } from '@/lib/utils/date';

interface MarketQuoteAnalysisCardProps {
  analysis: MarketQuoteAnalysis | null;
  isLoading: boolean;
  error: string | null;
}

export function MarketQuoteAnalysisCard({
  analysis,
  isLoading,
  error
}: MarketQuoteAnalysisCardProps) {
  // Get sentiment icon based on sentiment value
  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish':
        return <ArrowUpCircle className="h-5 w-5 text-green-500" />;
      case 'bearish':
        return <ArrowDownCircle className="h-5 w-5 text-red-500" />;
      default:
        return <MinusCircle className="h-5 w-5 text-yellow-500" />;
    }
  };

  // Get recommendation color based on value
  const getRecommendationColor = (recommendation: string) => {
    switch (recommendation) {
      case 'buy':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100';
      case 'sell':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100';
      default:
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100';
    }
  };

  // Get risk level color
  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'high':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100';
      case 'low':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100';
    }
  };

  // Format for loading state
  if (isLoading) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>
            <Skeleton className="h-8 w-3/4" />
          </CardTitle>
          <CardDescription>
            <Skeleton className="h-4 w-1/2" />
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-36 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  // Format for error state
  if (error) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="text-red-500">Analysis Error</CardTitle>
          <CardDescription>Unable to load market quote analysis</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-md text-red-800 dark:text-red-200">
            {error}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Format for no data state
  if (!analysis) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Market Quote Analysis</CardTitle>
          <CardDescription>No analysis data available</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-md">
            No market quote analysis data is currently available. Please check your selections and try again.
          </div>
        </CardContent>
      </Card>
    );
  }

  // Get all tickers from analysis
  const tickers = Object.keys(analysis.ticker_analysis || {});

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Market Quote Analysis</CardTitle>
            <CardDescription>
              {analysis.timestamp && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
                  <Clock className="h-3 w-3" /> {formatTimestamp(new Date(analysis.timestamp).getTime())}
                </span>
              )}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge 
              variant="outline" 
              className={
                analysis.market_overview.sentiment === 'bullish' 
                  ? 'bg-green-50 text-green-700 border-green-200 dark:bg-green-900/20 dark:border-green-800' 
                  : analysis.market_overview.sentiment === 'bearish' 
                  ? 'bg-red-50 text-red-700 border-red-200 dark:bg-red-900/20 dark:border-red-800' 
                  : 'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800'
              }
            >
              <span className="flex items-center gap-1">
                {getSentimentIcon(analysis.market_overview.sentiment)}
                {analysis.market_overview.sentiment.charAt(0).toUpperCase() + analysis.market_overview.sentiment.slice(1)}
              </span>
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Market Overview Section */}
        <div className="mb-6">
          <h3 className="text-lg font-medium mb-2">Market Overview</h3>
          <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-md">
            <p className="mb-3">{analysis.market_overview.market_condition}</p>
            <div className="space-y-1">
              {analysis.market_overview.key_observations.map((observation, index) => (
                <div key={index} className="flex items-start gap-2">
                  <div className="mt-1">•</div>
                  <p className="text-sm">{observation}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Ticker Analysis Section */}
        <div className="mb-6">
          <h3 className="text-lg font-medium mb-2">Ticker Analysis</h3>
          <Tabs defaultValue={tickers[0]}>
            <TabsList className="mb-2 flex flex-wrap h-auto">
              {tickers.map(ticker => (
                <TabsTrigger key={ticker} value={ticker} className="mb-1">
                  <span className="flex items-center gap-1">
                    {ticker}
                    {getSentimentIcon(analysis.ticker_analysis[ticker].sentiment)}
                  </span>
                </TabsTrigger>
              ))}
            </TabsList>
            
            {tickers.map(ticker => {
              const tickerData = analysis.ticker_analysis[ticker];
              return (
                <TabsContent key={ticker} value={ticker}>
                  <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-md">
                    <div className="flex flex-wrap gap-2 mb-3">
                      <Badge className={getRecommendationColor(tickerData.recommendation)}>
                        {tickerData.recommendation.toUpperCase()}
                      </Badge>
                      <Badge className={getRiskColor(tickerData.risk_level)}>
                        {tickerData.risk_level.toUpperCase()} RISK
                      </Badge>
                    </div>
                    
                    <div className="mb-3 flex flex-wrap gap-4">
                      <div className="flex items-center gap-1">
                        <Target className="h-4 w-4 text-blue-500" />
                        <span className="text-sm font-medium">Short-term: ${tickerData.price_target.short_term}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Target className="h-4 w-4 text-purple-500" />
                        <span className="text-sm font-medium">Long-term: ${tickerData.price_target.long_term}</span>
                      </div>
                    </div>
                    
                    <div className="space-y-1">
                      {tickerData.key_insights.map((insight, index) => (
                        <div key={index} className="flex items-start gap-2">
                          <div className="mt-1">•</div>
                          <p className="text-sm">{insight}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </TabsContent>
              );
            })}
          </Tabs>
        </div>

        {/* Trading Opportunities Section */}
        {analysis.trading_opportunities && analysis.trading_opportunities.length > 0 && (
          <div className="mb-6">
            <h3 className="text-lg font-medium mb-2">Trading Opportunities</h3>
            <div className="space-y-3">
              {analysis.trading_opportunities.map((opportunity, index) => (
                <div key={index} className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-md">
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className="h-5 w-5 text-amber-500" />
                    <h4 className="font-medium text-base">{opportunity.ticker}: {opportunity.strategy}</h4>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-2">
                    <div className="text-sm"><span className="font-medium">Time Horizon:</span> {opportunity.time_horizon}</div>
                    <div className="text-sm"><span className="font-medium">Risk/Reward:</span> {opportunity.risk_reward_ratio}</div>
                  </div>
                  <div className="text-sm">
                    <span className="font-medium">Rationale:</span> {opportunity.rationale}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Overall Recommendation */}
        <div>
          <h3 className="text-lg font-medium mb-2">Overall Recommendation</h3>
          <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-md text-blue-800 dark:text-blue-200">
            {analysis.overall_recommendation}
          </div>
        </div>
      </CardContent>
    </Card>
  );
} 