'use client';

import React, { useState, useEffect } from 'react';
import { useMarketQuoteAnalysis } from '@/hooks/useMarketQuoteAnalysis';
import { MarketQuoteAnalysisCard } from '@/components/market-quotes/MarketQuoteAnalysisCard';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent } from '@/components/ui/card';
import { Search, RefreshCw } from 'lucide-react';
import { MarketQuoteAnalysisType } from '@/app/api/agents/market-quotes/route';
import { Badge } from '@/components/ui/badge';

export default function MarketQuotesPage() {
  // Default tickers
  const defaultTickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN'];
  
  // State for form inputs
  const [tickerInput, setTickerInput] = useState<string>(defaultTickers.join(', '));
  const [analysisType, setAnalysisType] = useState<MarketQuoteAnalysisType>('technical');
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  
  // Custom hook for market quote analysis
  const {
    analysis,
    isLoading,
    error,
    refreshAnalysis
  } = useMarketQuoteAnalysis({
    initialTickers: defaultTickers,
    analysisType,
    autoLoad: true
  });
  
  // Handle submit for analysis
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    // Parse tickers from input
    const tickers = tickerInput
      .split(',')
      .map(ticker => ticker.trim().toUpperCase())
      .filter(ticker => ticker.length > 0);
    
    if (tickers.length === 0) {
      return;
    }
    
    // Update recent searches
    const tickerString = tickers.join(', ');
    setRecentSearches(prev => {
      const newSearches = [tickerString, ...prev.filter(item => item !== tickerString)];
      return newSearches.slice(0, 5); // Keep only 5 most recent
    });
    
    // Run analysis
    refreshAnalysis(tickers, analysisType);
  };
  
  // Handle clicking on a recent search
  const handleRecentSearchClick = (search: string) => {
    setTickerInput(search);
    
    const tickers = search
      .split(',')
      .map(ticker => ticker.trim())
      .filter(ticker => ticker.length > 0);
    
    refreshAnalysis(tickers, analysisType);
  };
  
  // Load recent searches from localStorage on initial load
  useEffect(() => {
    const savedSearches = localStorage.getItem('market-quote-recent-searches');
    if (savedSearches) {
      try {
        const parsed = JSON.parse(savedSearches);
        if (Array.isArray(parsed)) {
          setRecentSearches(parsed.slice(0, 5));
        }
      } catch (e) {
        console.error('Error parsing saved searches:', e);
      }
    }
  }, []);
  
  // Save recent searches to localStorage when they change
  useEffect(() => {
    localStorage.setItem('market-quote-recent-searches', JSON.stringify(recentSearches));
  }, [recentSearches]);
  
  return (
    <div className="container mx-auto p-4">
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold">Market Quote Analysis</h1>
          <p className="text-muted-foreground mt-1">
            Analyze real-time market quotes with AI to get trading insights and recommendations.
          </p>
        </div>
        
        {/* Search Form */}
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2">
                  <label htmlFor="ticker-input" className="block text-sm font-medium mb-1">
                    Ticker Symbols
                  </label>
                  <div className="relative">
                    <Input
                      id="ticker-input"
                      placeholder="Enter ticker symbols (e.g. AAPL, MSFT, GOOGL)"
                      value={tickerInput}
                      onChange={(e) => setTickerInput(e.target.value)}
                      className="pl-10"
                    />
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Separate multiple symbols with commas
                  </p>
                </div>
                
                <div>
                  <label htmlFor="analysis-type" className="block text-sm font-medium mb-1">
                    Analysis Type
                  </label>
                  <Select
                    value={analysisType}
                    onValueChange={(value) => setAnalysisType(value as MarketQuoteAnalysisType)}
                  >
                    <SelectTrigger id="analysis-type">
                      <SelectValue placeholder="Select analysis type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="basic">Basic</SelectItem>
                      <SelectItem value="technical">Technical</SelectItem>
                      <SelectItem value="fundamental">Fundamental</SelectItem>
                      <SelectItem value="comprehensive">Comprehensive</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="flex justify-end">
                <Button 
                  type="submit" 
                  disabled={isLoading}
                  className="flex items-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>Analyze Quotes</>
                  )}
                </Button>
              </div>
            </form>
            
            {/* Recent Searches */}
            {recentSearches.length > 0 && (
              <div className="mt-4">
                <p className="text-sm font-medium mb-2">Recent Searches:</p>
                <div className="flex flex-wrap gap-2">
                  {recentSearches.map((search, index) => (
                    <Badge 
                      key={index}
                      variant="outline"
                      className="cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800"
                      onClick={() => handleRecentSearchClick(search)}
                    >
                      {search}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Analysis Results */}
        <MarketQuoteAnalysisCard
          analysis={analysis}
          isLoading={isLoading}
          error={error}
        />
      </div>
    </div>
  );
} 