'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

interface OptionsAnalysisCardProps {
  ticker: string;
  analysis: any | null;
  isLoading: boolean;
  error: string | null;
}

export function OptionsAnalysisCard({
  ticker,
  analysis,
  isLoading,
  error
}: OptionsAnalysisCardProps) {
  // Function to determine color based on sentiment
  const getSentimentColor = (sentiment: string) => {
    switch (sentiment?.toLowerCase()) {
      case 'bullish':
        return 'bg-green-500';
      case 'bearish':
        return 'bg-red-500';
      case 'neutral':
      default:
        return 'bg-blue-500';
    }
  };

  // Function to format confidence
  const formatConfidence = (confidence: number) => {
    // If confidence is 0-1 decimal, multiply by 100 for percentage
    if (confidence <= 1) {
      return `${(confidence * 100).toFixed(1)}%`;
    }
    return `${confidence.toFixed(1)}%`;
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Options Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Options Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="p-4 bg-red-50 text-red-600 rounded-md">
            Error: {error}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!analysis) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Options Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="p-4 bg-gray-50 text-gray-600 rounded-md">
            No analysis available. Please click the "Analyze" button to generate an options analysis.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex justify-between items-center">
          <span>Options Analysis: {ticker}</span>
          <div className="flex space-x-2">
            <Badge className={getSentimentColor(analysis.overall_sentiment || analysis.market_conditions?.sentiment)}>
              {analysis.overall_sentiment || analysis.market_conditions?.sentiment || 'Neutral'}
            </Badge>
            <Badge variant="outline">
              Confidence: {formatConfidence(analysis.confidence || 0)}
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>

      <CardContent>
        <Tabs defaultValue="market" className="w-full">
          <TabsList className="w-full">
            <TabsTrigger value="market" className="w-1/3">
              Market Conditions
            </TabsTrigger>
            <TabsTrigger value="strategies" className="w-1/3">
              Strategies
            </TabsTrigger>
            <TabsTrigger value="reasoning" className="w-1/3">
              Reasoning
            </TabsTrigger>
          </TabsList>

          {/* Market Conditions Tab */}
          <TabsContent value="market">
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-gray-50 rounded-md">
                  <div className="text-sm text-gray-500">Put/Call Ratio</div>
                  <div className="text-xl font-semibold">
                    {analysis.market_conditions?.put_call_ratio.toFixed(2) || 'N/A'}
                  </div>
                </div>
                
                <div className="p-4 bg-gray-50 rounded-md">
                  <div className="text-sm text-gray-500">IV Skew</div>
                  <div className="text-xl font-semibold">
                    {analysis.market_conditions?.implied_volatility_skew.toFixed(2) || 'N/A'}
                  </div>
                </div>
                
                <div className="p-4 bg-gray-50 rounded-md">
                  <div className="text-sm text-gray-500">Market Condition</div>
                  <div className="text-xl font-semibold">
                    {analysis.market_conditions?.market_condition || 'Normal'}
                  </div>
                </div>
              </div>

              {/* Key Observations */}
              {analysis.market_conditions?.key_observations && (
                <div className="mt-4">
                  <h3 className="text-md font-semibold mb-2">Key Observations</h3>
                  <ul className="list-disc pl-5 space-y-1">
                    {analysis.market_conditions.key_observations.map((observation: string, index: number) => (
                      <li key={index} className="text-sm">
                        {observation}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Greeks */}
              {analysis.greeks && (
                <div className="mt-4">
                  <h3 className="text-md font-semibold mb-2">Options Greeks</h3>
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Greek</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Call</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Put</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      <tr>
                        <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900">Delta</td>
                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{analysis.greeks.call_delta.toFixed(3)}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{analysis.greeks.put_delta.toFixed(3)}</td>
                      </tr>
                      <tr>
                        <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900">Gamma</td>
                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{analysis.greeks.call_gamma.toFixed(3)}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{analysis.greeks.put_gamma.toFixed(3)}</td>
                      </tr>
                      <tr>
                        <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900">Theta</td>
                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{analysis.greeks.call_theta.toFixed(3)}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{analysis.greeks.put_theta.toFixed(3)}</td>
                      </tr>
                      <tr>
                        <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900">Vega</td>
                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{analysis.greeks.call_vega.toFixed(3)}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{analysis.greeks.put_vega.toFixed(3)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Strategies Tab */}
          <TabsContent value="strategies">
            <div className="space-y-4">
              {/* Handle different response formats */}
              {analysis.recommended_strategies ? (
                // New format - array of strategies
                analysis.recommended_strategies.map((strategy: any, index: number) => (
                  <div key={index} className="p-4 bg-gray-50 rounded-md">
                    <h3 className="text-lg font-semibold">
                      {strategy.strategy_name || 'Strategy ' + (index + 1)}
                    </h3>
                    <p className="mt-1 text-sm text-gray-600">{strategy.description}</p>
                    
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                      <div>
                        <div className="text-xs text-gray-500">Implementation</div>
                        <div className="text-sm">{strategy.implementation}</div>
                      </div>
                      
                      <div>
                        <div className="text-xs text-gray-500">Risk Level</div>
                        <div>
                          <Badge className={
                            strategy.risk_level === 'high' ? 'bg-red-500' :
                            strategy.risk_level === 'medium' ? 'bg-yellow-500' : 'bg-green-500'
                          }>
                            {strategy.risk_level || 'Medium'}
                          </Badge>
                        </div>
                      </div>
                    </div>
                    
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2">
                      <div>
                        <div className="text-xs text-gray-500">Max Profit</div>
                        <div className="text-sm">{strategy.max_profit}</div>
                      </div>
                      
                      <div>
                        <div className="text-xs text-gray-500">Max Loss</div>
                        <div className="text-sm">{strategy.max_loss}</div>
                      </div>
                      
                      <div>
                        <div className="text-xs text-gray-500">Break Even</div>
                        <div className="text-sm">{strategy.break_even}</div>
                      </div>
                    </div>
                    
                    <div className="mt-3">
                      <div className="text-xs text-gray-500">Exit Strategy</div>
                      <div className="text-sm">{strategy.exit_strategy}</div>
                    </div>
                  </div>
                ))
              ) : analysis.recommended_strategy ? (
                // Old format - single strategy object
                <div className="p-4 bg-gray-50 rounded-md">
                  <h3 className="text-lg font-semibold">
                    {analysis.recommended_strategy.name || 'Recommended Strategy'}
                  </h3>
                  <p className="mt-1 text-sm text-gray-600">{analysis.recommended_strategy.description}</p>
                  
                  {/* Legs */}
                  {analysis.recommended_strategy.legs && (
                    <div className="mt-3">
                      <div className="text-xs text-gray-500">Options Legs</div>
                      <ul className="list-disc pl-5 space-y-1">
                        {analysis.recommended_strategy.legs.map((leg: any, index: number) => (
                          <li key={index} className="text-sm">
                            {leg.type} {leg.option_type} @ strike ${leg.strike}, expiration {leg.expiration}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                    <div>
                      <div className="text-xs text-gray-500">Max Profit</div>
                      <div className="text-sm">{analysis.recommended_strategy.max_profit}</div>
                    </div>
                    
                    <div>
                      <div className="text-xs text-gray-500">Max Loss</div>
                      <div className="text-sm">{analysis.recommended_strategy.max_loss}</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-gray-100 text-gray-500 rounded-md">
                  No specific strategy recommendations available.
                </div>
              )}
            </div>
          </TabsContent>

          {/* Reasoning Tab */}
          <TabsContent value="reasoning">
            <div className="p-4 bg-gray-50 rounded-md">
              <p className="whitespace-pre-line">{analysis.reasoning}</p>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
} 