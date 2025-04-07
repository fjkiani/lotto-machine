'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AgentType, AgentResponse, OrchestratedAnalysisResult } from '@/lib/connectors/agent-hub';
import { Loader2, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';
import { useAgents } from '@/hooks/useAgents';

// Agent icon mapping
const AGENT_ICONS: Record<AgentType, React.ReactNode> = {
  [AgentType.TECHNICAL_ANALYST]: <span className="text-blue-500">📈</span>,
  [AgentType.OPTIONS_SPECIALIST]: <span className="text-purple-500">🔄</span>,
  [AgentType.MARKET_OVERVIEW]: <span className="text-green-500">🌎</span>,
  [AgentType.NEWS_EVALUATOR]: <span className="text-yellow-500">📰</span>,
  [AgentType.RISK_MANAGER]: <span className="text-red-500">⚠️</span>,
  [AgentType.PORTFOLIO_STRATEGIST]: <span className="text-indigo-500">📊</span>,
  [AgentType.SENTIMENT_ANALYZER]: <span className="text-orange-500">😊</span>,
};

// Agent display names
const AGENT_NAMES: Record<AgentType, string> = {
  [AgentType.TECHNICAL_ANALYST]: 'Technical Analyst',
  [AgentType.OPTIONS_SPECIALIST]: 'Options Specialist',
  [AgentType.MARKET_OVERVIEW]: 'Market Overview',
  [AgentType.NEWS_EVALUATOR]: 'News Evaluator',
  [AgentType.RISK_MANAGER]: 'Risk Manager',
  [AgentType.PORTFOLIO_STRATEGIST]: 'Portfolio Strategist',
  [AgentType.SENTIMENT_ANALYZER]: 'Sentiment Analyzer',
};

// Sentiment color mapping
const SENTIMENT_COLORS = {
  bullish: 'bg-green-100 text-green-800',
  bearish: 'bg-red-100 text-red-800',
  neutral: 'bg-gray-100 text-gray-800',
};

interface AgentAnalysisCardProps {
  ticker: string;
  period?: string;
  agents?: AgentType[];
  defaultAgent?: AgentType;
  model?: 'openai' | 'gemini';
}

export function AgentAnalysisCard({
  ticker,
  period = '1y',
  agents = [AgentType.TECHNICAL_ANALYST, AgentType.OPTIONS_SPECIALIST, AgentType.MARKET_OVERVIEW],
  defaultAgent = AgentType.TECHNICAL_ANALYST,
  model = 'gemini'
}: AgentAnalysisCardProps) {
  const [expanded, setExpanded] = useState<boolean>(false);
  const { orchestrateAgents, singleAgent } = useAgents();
  const [activeTab, setActiveTab] = useState<string>('orchestrated');
  const [activeAgentTab, setActiveAgentTab] = useState<string>(defaultAgent);
  
  // Run analysis when the component loads
  useState(() => {
    runOrchestrationAnalysis();
  });
  
  // Run orchestrated analysis
  const runOrchestrationAnalysis = async () => {
    await orchestrateAgents.execute({
      agents,
      ticker,
      period,
      model,
      sequential: false,
      primaryAgent: defaultAgent
    });
  };
  
  // Run single agent analysis
  const runSingleAgentAnalysis = async (agent: AgentType) => {
    await singleAgent.execute({
      agent,
      ticker,
      period,
      model
    });
  };
  
  // Extract sentiment from analysis
  const getSentiment = (data: OrchestratedAnalysisResult | AgentResponse | null): 'bullish' | 'bearish' | 'neutral' => {
    if (!data) return 'neutral';
    
    if ('unified_analysis' in data) {
      return data.unified_analysis.sentiment;
    }
    
    if (data.analysis?.overall_sentiment) {
      return data.analysis.overall_sentiment;
    }
    
    if (data.analysis?.sentiment) {
      return data.analysis.sentiment;
    }
    
    if (data.analysis?.trend_analysis?.primary_trend) {
      return data.analysis.trend_analysis.primary_trend;
    }
    
    return 'neutral';
  };
  
  // Get confidence score
  const getConfidence = (data: OrchestratedAnalysisResult | AgentResponse | null): number => {
    if (!data) return 0;
    
    if ('unified_analysis' in data) {
      return Math.round(data.unified_analysis.confidence * 100);
    }
    
    if (typeof data.confidence === 'number') {
      return Math.round(data.confidence * 100);
    }
    
    return 0;
  };
  
  // Determine if we're loading
  const isLoading = orchestrateAgents.isLoading || singleAgent.isLoading;
  
  // Get active data
  const activeData = activeTab === 'orchestrated' 
    ? orchestrateAgents.data 
    : singleAgent.data;
  
  // Get sentiment for display
  const sentiment = getSentiment(activeData);
  const confidence = getConfidence(activeData);
  
  // Format datetime
  const formatTimestamp = (timestamp: string) => {
    if (!timestamp) return '';
    return new Date(timestamp).toLocaleString();
  };
  
  return (
    <Card className="w-full shadow-md">
      <CardHeader>
        <div className="flex justify-between items-center">
          <div>
            <CardTitle>AI Analysis for {ticker}</CardTitle>
            <CardDescription>
              Multi-agent LLM analysis for {period} period
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline">
              {model === 'gemini' ? 'Gemini' : 'GPT-4o'}
            </Badge>
            {!isLoading ? (
              <Button 
                variant="outline" 
                size="icon" 
                onClick={() => activeTab === 'orchestrated' ? runOrchestrationAnalysis() : runSingleAgentAnalysis(activeAgentTab as AgentType)}
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            ) : (
              <Button variant="outline" size="icon" disabled>
                <Loader2 className="h-4 w-4 animate-spin" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        <Tabs defaultValue="orchestrated" value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="w-full">
            <TabsTrigger value="orchestrated" className="w-1/2">Orchestrated Analysis</TabsTrigger>
            <TabsTrigger value="individual" className="w-1/2">Individual Agents</TabsTrigger>
          </TabsList>
          
          <TabsContent value="orchestrated">
            {orchestrateAgents.isLoading ? (
              <div className="py-8 flex justify-center items-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : orchestrateAgents.error ? (
              <div className="py-4 text-center text-red-500">
                {orchestrateAgents.error}
              </div>
            ) : orchestrateAgents.data ? (
              <div className="space-y-4 py-2">
                {/* Unified Analysis Summary */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h3 className="text-lg font-semibold">Unified Analysis</h3>
                    <Badge className={SENTIMENT_COLORS[sentiment]}>
                      {sentiment.charAt(0).toUpperCase() + sentiment.slice(1)} ({confidence}% confidence)
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {orchestrateAgents.data.unified_analysis.summary}
                  </p>
                </div>
                
                {/* Recommendation */}
                <div className="p-3 bg-muted rounded-md">
                  <div className="flex justify-between items-center">
                    <h4 className="font-medium">Recommendation</h4>
                    <Badge variant="secondary">
                      {orchestrateAgents.data.recommendation.action.toUpperCase()}
                    </Badge>
                  </div>
                  <p className="text-sm mt-1">
                    {orchestrateAgents.data.recommendation.reasoning}
                  </p>
                </div>
                
                {/* Key Insights */}
                {orchestrateAgents.data.unified_analysis.key_insights.length > 0 && (
                  <div className="space-y-1">
                    <h4 className="font-medium">Key Insights</h4>
                    <ul className="text-sm space-y-1 list-disc pl-5">
                      {orchestrateAgents.data.unified_analysis.key_insights.slice(0, expanded ? undefined : 3).map((insight, i) => (
                        <li key={i}>{insight}</li>
                      ))}
                    </ul>
                    {orchestrateAgents.data.unified_analysis.key_insights.length > 3 && (
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="text-xs mt-1"
                        onClick={() => setExpanded(!expanded)}
                      >
                        {expanded ? 'Show Less' : `Show ${orchestrateAgents.data.unified_analysis.key_insights.length - 3} More`}
                        {expanded ? <ChevronUp className="ml-1 h-3 w-3" /> : <ChevronDown className="ml-1 h-3 w-3" />}
                      </Button>
                    )}
                  </div>
                )}
                
                {/* Contradictions */}
                {orchestrateAgents.data.unified_analysis.contradictions.length > 0 && (
                  <div className="space-y-1">
                    <h4 className="font-medium">Contradictions</h4>
                    <ul className="text-sm space-y-1 list-disc pl-5">
                      {orchestrateAgents.data.unified_analysis.contradictions.map((contradiction, i) => (
                        <li key={i} className="text-amber-700">{contradiction}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-6 text-center text-muted-foreground">
                Click refresh to run the analysis
              </div>
            )}
          </TabsContent>
          
          <TabsContent value="individual">
            <Tabs value={activeAgentTab} onValueChange={setActiveAgentTab}>
              <TabsList className="w-full mt-2">
                {agents.map(agent => (
                  <TabsTrigger key={agent} value={agent} className={`${agents.length > 3 ? 'text-xs' : ''}`}>
                    {AGENT_ICONS[agent]} {AGENT_NAMES[agent]}
                  </TabsTrigger>
                ))}
              </TabsList>
              
              {agents.map(agent => (
                <TabsContent key={agent} value={agent}>
                  <div className="py-2">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={() => runSingleAgentAnalysis(agent)}
                      disabled={singleAgent.isLoading}
                      className="mb-3"
                    >
                      {singleAgent.isLoading ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : null}
                      Analyze with {AGENT_NAMES[agent]}
                    </Button>
                    
                    {singleAgent.data?.agent_type === agent ? (
                      <div className="space-y-3">
                        <div className="flex justify-between items-center">
                          <h3 className="text-lg font-semibold">{AGENT_NAMES[agent]} Analysis</h3>
                          <Badge className={SENTIMENT_COLORS[getSentiment(singleAgent.data)]}>
                            {getSentiment(singleAgent.data).charAt(0).toUpperCase() + getSentiment(singleAgent.data).slice(1)} 
                            ({getConfidence(singleAgent.data)}% confidence)
                          </Badge>
                        </div>
                        
                        <div className="text-sm">
                          {renderAgentAnalysis(agent, singleAgent.data)}
                        </div>
                        
                        <div className="text-xs text-muted-foreground text-right">
                          Analyzed at {formatTimestamp(singleAgent.data.analysis_timestamp)}
                        </div>
                      </div>
                    ) : (
                      <div className="py-6 text-center text-muted-foreground">
                        Run the analysis to see results from this agent
                      </div>
                    )}
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          </TabsContent>
        </Tabs>
      </CardContent>
      
      <CardFooter className="text-xs text-muted-foreground border-t pt-3">
        <div className="w-full flex justify-between items-center">
          <div>
            Results based on data available as of {formatTimestamp(activeData?.analysis_timestamp || new Date().toISOString())}
          </div>
          <div>
            Powered by {model === 'gemini' ? 'Google Gemini' : 'OpenAI GPT-4o'}
          </div>
        </div>
      </CardFooter>
    </Card>
  );
}

/**
 * Render agent-specific analysis data
 */
function renderAgentAnalysis(agentType: AgentType, data: AgentResponse | null) {
  if (!data || !data.analysis) return <p>No analysis data available</p>;
  
  const analysis = data.analysis;
  
  switch (agentType) {
    case AgentType.TECHNICAL_ANALYST:
      return (
        <div className="space-y-2">
          {/* Trend analysis */}
          {analysis.trend_analysis && (
            <div className="p-2 bg-muted rounded-md">
              <h4 className="font-medium">Trend Analysis</h4>
              <p>Primary Trend: <span className="font-medium">{analysis.trend_analysis.primary_trend}</span></p>
              <p>Strength: {analysis.trend_analysis.trend_strength}/10</p>
              <p>Duration: {analysis.trend_analysis.trend_duration}</p>
            </div>
          )}
          
          {/* Support/Resistance */}
          {analysis.support_resistance && (
            <div className="p-2 bg-muted rounded-md">
              <h4 className="font-medium">Support & Resistance</h4>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <p className="text-xs font-medium">Support Levels</p>
                  <ul className="list-disc pl-4 text-xs">
                    {analysis.support_resistance.strong_support_levels.map((level: number, i: number) => (
                      <li key={i}>{level}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs font-medium">Resistance Levels</p>
                  <ul className="list-disc pl-4 text-xs">
                    {analysis.support_resistance.strong_resistance_levels.map((level: number, i: number) => (
                      <li key={i}>{level}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
          
          {/* RSI */}
          {analysis.indicator_analysis?.rsi && (
            <div className="p-2 bg-muted rounded-md">
              <h4 className="font-medium">RSI Analysis</h4>
              <p>Condition: {analysis.indicator_analysis.rsi.condition}</p>
              <p>Value: {analysis.indicator_analysis.rsi.value}</p>
              <p className="text-xs">{analysis.indicator_analysis.rsi.interpretation}</p>
            </div>
          )}
          
          {/* Summary */}
          {analysis.summary && (
            <div className="mt-2">
              <p className="italic">{analysis.summary}</p>
            </div>
          )}
        </div>
      );
      
    case AgentType.OPTIONS_SPECIALIST:
      return (
        <div className="space-y-2">
          {/* Market Conditions */}
          {analysis.market_conditions && (
            <div className="p-2 bg-muted rounded-md">
              <h4 className="font-medium">Market Conditions</h4>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <p>Put/Call Ratio:</p>
                <p className="font-medium">{analysis.market_conditions.put_call_ratio.toFixed(2)}</p>
                
                <p>IV Skew:</p>
                <p className="font-medium">{analysis.market_conditions.implied_volatility_skew.toFixed(2)}</p>
                
                <p>Sentiment:</p>
                <p className="font-medium">{analysis.market_conditions.sentiment}</p>
                
                <p>Market State:</p>
                <p className="font-medium">{analysis.market_conditions.market_condition}</p>
              </div>
            </div>
          )}
          
          {/* Recommended Strategy */}
          {analysis.recommended_strategy && (
            <div className="p-2 bg-muted rounded-md">
              <h4 className="font-medium">Recommended Strategy</h4>
              <p className="font-medium">{analysis.recommended_strategy.name}</p>
              <p className="text-xs mt-1">{analysis.recommended_strategy.description}</p>
              
              {analysis.recommended_strategy.legs.length > 0 && (
                <>
                  <p className="text-xs font-medium mt-2">Strategy Legs:</p>
                  <ul className="list-disc pl-4 text-xs">
                    {analysis.recommended_strategy.legs.map((leg: any, i: number) => (
                      <li key={i}>
                        {leg.type} {leg.option_type} at strike {leg.strike} (exp: {leg.expiration})
                      </li>
                    ))}
                  </ul>
                </>
              )}
              
              <div className="grid grid-cols-2 gap-x-4 mt-2 text-xs">
                <p>Max Profit:</p>
                <p className="font-medium text-green-600">{analysis.recommended_strategy.max_profit}</p>
                
                <p>Max Loss:</p>
                <p className="font-medium text-red-600">{analysis.recommended_strategy.max_loss}</p>
              </div>
            </div>
          )}
          
          {/* Greeks */}
          {analysis.greeks && (
            <div className="p-2 bg-muted rounded-md">
              <h4 className="font-medium">Greeks</h4>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <p className="font-medium">Call Greeks</p>
                  <div className="grid grid-cols-2 gap-x-2">
                    <p>Delta:</p><p>{analysis.greeks.call_delta.toFixed(2)}</p>
                    <p>Gamma:</p><p>{analysis.greeks.call_gamma.toFixed(4)}</p>
                    <p>Theta:</p><p>{analysis.greeks.call_theta.toFixed(2)}</p>
                    <p>Vega:</p><p>{analysis.greeks.call_vega.toFixed(2)}</p>
                  </div>
                </div>
                <div>
                  <p className="font-medium">Put Greeks</p>
                  <div className="grid grid-cols-2 gap-x-2">
                    <p>Delta:</p><p>{analysis.greeks.put_delta.toFixed(2)}</p>
                    <p>Gamma:</p><p>{analysis.greeks.put_gamma.toFixed(4)}</p>
                    <p>Theta:</p><p>{analysis.greeks.put_theta.toFixed(2)}</p>
                    <p>Vega:</p><p>{analysis.greeks.put_vega.toFixed(2)}</p>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {/* Reasoning */}
          {analysis.reasoning && (
            <div className="mt-2">
              <h4 className="text-xs font-medium">Analysis Reasoning:</h4>
              <p className="text-xs italic">{analysis.reasoning}</p>
            </div>
          )}
        </div>
      );
      
    case AgentType.MARKET_OVERVIEW:
      return (
        <div className="space-y-2">
          {/* Summary */}
          {analysis.summary && (
            <div className="p-2 bg-muted rounded-md">
              <h4 className="font-medium">Market Summary</h4>
              <p className="text-sm">{analysis.summary}</p>
            </div>
          )}
          
          {/* Key Factors */}
          {analysis.key_factors && analysis.key_factors.length > 0 && (
            <div className="p-2 bg-muted rounded-md">
              <h4 className="font-medium">Key Market Factors</h4>
              <ul className="list-disc pl-4 text-sm">
                {analysis.key_factors.map((factor: string, i: number) => (
                  <li key={i}>{factor}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      );
      
    default:
      // Generic display for other agent types
      return (
        <div>
          <pre className="text-xs overflow-auto p-2 bg-muted rounded-md max-h-[300px]">
            {JSON.stringify(analysis, null, 2)}
          </pre>
        </div>
      );
  }
} 