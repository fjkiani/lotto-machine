'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { OptionsChainTable } from '@/components/options/OptionsChainTable';
import { OptionsAnalysisCard } from '@/components/options/OptionsAnalysisCard';
import { useOptionsChain } from '@/hooks/useOptionsChain';
import { useOptionsAnalysis } from '@/hooks/useOptionsAnalysis';
import { RiskTolerance } from '@/hooks/useOptionsAnalysis';
import { Loader2 } from 'lucide-react';

export default function OptionsAnalysisPage() {
  // State for user inputs
  const [ticker, setTicker] = useState<string>('AAPL');
  const [expiration, setExpiration] = useState<string>('');
  const [riskTolerance, setRiskTolerance] = useState<RiskTolerance>('medium');
  
  // Fetch options chain data
  const { 
    data: optionsData, 
    expirationDates,
    isLoading: isLoadingOptions, 
    error: optionsError,
    fetchOptionsChain
  } = useOptionsChain({
    autoFetch: false
  });
  
  // Options analysis state
  const {
    analysis,
    isLoading: isAnalyzing,
    error: analysisError,
    analyzeOptions
  } = useOptionsAnalysis();
  
  // Handle search click
  const handleSearch = () => {
    if (ticker.trim() === '') return;
    fetchOptionsChain(ticker);
  };
  
  // Handle analysis click
  const handleAnalyze = () => {
    if (ticker.trim() === '' || !expiration) return;
    analyzeOptions(ticker, riskTolerance, expiration);
  };
  
  // Handle expiration change
  const handleExpirationChange = (value: string) => {
    setExpiration(value);
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <h1 className="text-3xl font-bold">Options Analysis</h1>
      
      {/* Search and Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Analysis Controls</CardTitle>
          <CardDescription>
            Enter a ticker symbol to fetch options chain data, then select expiration date and analyze.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="text-sm font-medium mb-1 block">Ticker Symbol</label>
              <div className="flex space-x-2">
                <Input
                  placeholder="e.g. AAPL"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                />
                <Button onClick={handleSearch} disabled={isLoadingOptions || ticker.trim() === ''}>
                  {isLoadingOptions ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Loading
                    </>
                  ) : 'Fetch'}
                </Button>
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Expiration Date</label>
              <Select
                value={expiration}
                onValueChange={handleExpirationChange}
                disabled={!expirationDates || expirationDates.length === 0}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select expiration" />
                </SelectTrigger>
                <SelectContent>
                  {expirationDates?.map((date) => (
                    <SelectItem key={date} value={date}>
                      {new Date(date).toLocaleDateString()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label className="text-sm font-medium mb-1 block">Risk Tolerance</label>
              <Select
                value={riskTolerance}
                onValueChange={(value) => setRiskTolerance(value as RiskTolerance)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Risk tolerance" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low Risk</SelectItem>
                  <SelectItem value="medium">Medium Risk</SelectItem>
                  <SelectItem value="high">High Risk</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="flex items-end">
              <Button 
                className="w-full" 
                onClick={handleAnalyze} 
                disabled={isAnalyzing || !ticker || !expiration}
                variant="secondary"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Analyzing
                  </>
                ) : 'Analyze Options'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Options Chain Display */}
      <OptionsChainTable
        data={optionsData}
        isLoading={isLoadingOptions}
        error={optionsError}
        onExpirationChange={handleExpirationChange}
      />
      
      {/* Options Analysis Display */}
      <OptionsAnalysisCard
        ticker={ticker}
        analysis={analysis}
        isLoading={isAnalyzing}
        error={analysisError}
      />
    </div>
  );
} 