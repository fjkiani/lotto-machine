import { NextResponse } from 'next/server';
import { generateComprehensiveAnalysis } from '@/lib/connectors/llm';

/**
 * API route for analyzing data with an LLM
 * POST /api/llm/analyze
 */
export async function POST(request: Request) {
  try {
    // Parse request body
    const body = await request.json();
    const { prompt, model, temperature, responseFormat } = body;
    
    // Validate required parameters
    if (!prompt) {
      return NextResponse.json(
        { error: 'Missing required parameter: prompt' },
        { status: 400 }
      );
    }
    
    console.log(`[api/llm/analyze] Processing LLM analysis request using model: ${model || 'default'}`);
    console.log(`[api/llm/analyze] Prompt length: ${prompt.length} characters`);
    
    // Call the appropriate LLM API based on the model
    let result;
    
    if (model?.startsWith('gemini')) {
      // Call Gemini API
      result = await callGeminiAPI(prompt, {
        model: model || 'gemini-1.5-flash',
        temperature: temperature || 0.2,
        responseFormat: responseFormat || 'json'
      });
    } else {
      // Default to OpenAI API
      result = await callOpenAIAPI(prompt, {
        model: model || 'gpt-4o',
        temperature: temperature || 0.2,
        responseFormat: responseFormat || 'json'
      });
    }
    
    // Return the result
    return NextResponse.json({ 
      result,
      model: model || 'default',
      timestamp: new Date().toISOString()
    });
  } catch (error: any) {
    console.error('[api/llm/analyze] Error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to analyze with LLM',
        details: error.message || 'Unknown error'
      },
      { status: 500 }
    );
  }
}

interface GeminiRequestOptions {
  model: string;
  temperature: number;
  responseFormat?: string;
}

/**
 * Call the Gemini API
 */
async function callGeminiAPI(
  prompt: string,
  options: GeminiRequestOptions
): Promise<string> {
  // Check for API key
  const apiKey = process.env.GEMINI_API_KEY || process.env.NEXT_PUBLIC_GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error('Gemini API key not found in environment variables');
  }
  
  try {
    // Prepare the request
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${options.model}:generateContent?key=${apiKey}`;
    
    // Prepare the request body
    const requestBody = {
      contents: [{
        parts: [{
          text: prompt
        }]
      }],
      generationConfig: {
        temperature: options.temperature,
        topK: 64,
        topP: 0.95,
        maxOutputTokens: 8192,
        responseMimeType: options.responseFormat === 'json' ? 'application/json' : 'text/plain',
      }
    };
    
    console.log(`[api/llm/analyze] Calling Gemini API with model: ${options.model}`);
    
    // Make the API call
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Gemini API error: ${response.status}. ${errorText}`);
    }
    
    // Parse the response
    const data = await response.json();
    
    // Extract the content from the response
    let content = '';
    if (data.candidates && data.candidates.length > 0) {
      // Get the first candidate's content
      const candidate = data.candidates[0];
      
      if (candidate.content && candidate.content.parts && candidate.content.parts.length > 0) {
        // Extract the text from each part and join them
        content = candidate.content.parts.map((part: any) => part.text).join('');
      }
    }
    
    if (!content) {
      throw new Error('No content in Gemini API response');
    }
    
    console.log('[api/llm/analyze] Successfully received Gemini API response');
    
    return content;
  } catch (error) {
    console.error('[api/llm/analyze] Gemini API error:', error);
    throw error;
  }
}

interface OpenAIRequestOptions {
  model: string;
  temperature: number;
  responseFormat?: string;
}

/**
 * Call the OpenAI API
 */
async function callOpenAIAPI(
  prompt: string,
  options: OpenAIRequestOptions
): Promise<string> {
  // Check for API key
  const apiKey = process.env.OPENAI_API_KEY || process.env.NEXT_PUBLIC_OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OpenAI API key not found in environment variables');
  }
  
  try {
    // Prepare the request
    const url = 'https://api.openai.com/v1/chat/completions';
    
    // Prepare the request body
    const requestBody: any = {
      model: options.model,
      messages: [
        {
          role: 'system',
          content: 'You are a professional options trader and financial analyst providing detailed analysis.'
        },
        {
          role: 'user',
          content: prompt
        }
      ],
      temperature: options.temperature,
      max_tokens: 4000
    };
    
    // Add response format if needed
    if (options.responseFormat === 'json') {
      requestBody.response_format = { type: 'json_object' };
    }
    
    console.log(`[api/llm/analyze] Calling OpenAI API with model: ${options.model}`);
    
    // Make the API call
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`OpenAI API error: ${response.status}. ${errorText}`);
    }
    
    // Parse the response
    const data = await response.json();
    
    // Extract the content from the response
    const content = data.choices && data.choices.length > 0 ? data.choices[0].message.content : '';
    
    if (!content) {
      throw new Error('No content in OpenAI API response');
    }
    
    console.log('[api/llm/analyze] Successfully received OpenAI API response');
    
    return content;
  } catch (error) {
    console.error('[api/llm/analyze] OpenAI API error:', error);
    throw error;
  }
} 