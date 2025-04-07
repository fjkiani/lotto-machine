'use client';

import { useState } from 'react';
import { AgentAnalysisCard } from '@/components/analysis/AgentAnalysisCard';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { AgentType } from '@/lib/connectors/agent-hub';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CheckboxItem, Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

export default function AgentAnalysisPage() {
  const [ticker, setTicker] = useState<string>('AAPL');
  const [period, setPeriod] = useState<string>('1y');
  const [model, setModel] = useState<'openai' | 'gemini'>('gemini');
  const [selectedAgents, setSelectedAgents] = useState<AgentType[]>([
    AgentType.TECHNICAL_ANALYST,
    AgentType.OPTIONS_SPECIALIST,
    AgentType.MARKET_OVERVIEW
  ]);
  const [primaryAgent, setPrimaryAgent] = useState<AgentType>(AgentType.TECHNICAL_ANALYST);
  const [inputTicker, setInputTicker] = useState<string>('AAPL');
  
  // Available agent types for selection
  const availableAgentTypes = [
    AgentType.TECHNICAL_ANALYST,
    AgentType.OPTIONS_SPECIALIST,
    AgentType.MARKET_OVERVIEW,
    AgentType.RISK_MANAGER,
  ];
  
  // Handle agent selection change
  const handleAgentSelectionChange = (agent: AgentType, checked: boolean) => {
    if (checked) {
      setSelectedAgents([...selectedAgents, agent]);
    } else {
      setSelectedAgents(selectedAgents.filter(a => a !== agent));
      
      // If primary agent is being deselected, choose another one
      if (primaryAgent === agent && selectedAgents.length > 1) {
        setPrimaryAgent(selectedAgents.filter(a => a !== agent)[0]);
      }
    }
  };
  
  // Handle form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTicker(inputTicker);
  };
  
  return (
    <div className="container mx-auto py-8 space-y-8">
      <h1 className="text-3xl font-bold">AI Agent Analysis Hub</h1>
      <p className="text-muted-foreground">
        Leveraging specialized LLM agents for comprehensive financial analysis
      </p>
      
      <Card>
        <CardHeader>
          <CardTitle>Analysis Configuration</CardTitle>
          <CardDescription>
            Customize your analysis by selecting specific agents and setting parameters
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <div>
                  <Label htmlFor="ticker">Stock Ticker</Label>
                  <div className="flex gap-2 mt-1">
                    <Input 
                      id="ticker" 
                      value={inputTicker} 
                      onChange={(e) => setInputTicker(e.target.value.toUpperCase())} 
                      placeholder="Enter ticker symbol" 
                      className="uppercase"
                    />
                    <Button type="submit">Analyze</Button>
                  </div>
                </div>
                
                <div>
                  <Label htmlFor="period">Time Period</Label>
                  <Select value={period} onValueChange={setPeriod}>
                    <SelectTrigger id="period">
                      <SelectValue placeholder="Select time period" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1mo">1 Month</SelectItem>
                      <SelectItem value="3mo">3 Months</SelectItem>
                      <SelectItem value="6mo">6 Months</SelectItem>
                      <SelectItem value="1y">1 Year</SelectItem>
                      <SelectItem value="2y">2 Years</SelectItem>
                      <SelectItem value="5y">5 Years</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div>
                  <Label htmlFor="model">LLM Model</Label>
                  <Select value={model} onValueChange={(value: any) => setModel(value)}>
                    <SelectTrigger id="model">
                      <SelectValue placeholder="Select LLM model" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gemini">Google Gemini</SelectItem>
                      <SelectItem value="openai">OpenAI GPT-4o</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="space-y-4">
                <Label>Select Agents</Label>
                <div className="grid grid-cols-2 gap-3">
                  {availableAgentTypes.map((agent) => (
                    <div className="flex items-center space-x-2" key={agent}>
                      <Checkbox 
                        id={`agent-${agent}`} 
                        checked={selectedAgents.includes(agent)}
                        onCheckedChange={(checked) => handleAgentSelectionChange(agent, checked as boolean)}
                      />
                      <Label htmlFor={`agent-${agent}`} className="font-normal">
                        {agent.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}
                      </Label>
                    </div>
                  ))}
                </div>
                
                <div>
                  <Label htmlFor="primary-agent">Primary Agent (2x weight)</Label>
                  <Select 
                    value={primaryAgent} 
                    onValueChange={(value: any) => setPrimaryAgent(value)}
                    disabled={selectedAgents.length < 2}
                  >
                    <SelectTrigger id="primary-agent">
                      <SelectValue placeholder="Select primary agent" />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedAgents.map((agent) => (
                        <SelectItem key={agent} value={agent}>
                          {agent.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>
      
      <AgentAnalysisCard 
        ticker={ticker}
        period={period}
        agents={selectedAgents}
        defaultAgent={primaryAgent}
        model={model}
      />
      
      <div className="mt-8 text-center text-sm text-muted-foreground">
        <p>This analysis is powered by specialized LLM agents, each with domain expertise in different aspects of financial analysis.</p>
        <p>The orchestration system combines insights from multiple agents to provide a comprehensive analysis.</p>
      </div>
    </div>
  );
} 