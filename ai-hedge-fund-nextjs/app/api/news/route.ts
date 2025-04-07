import { NextResponse } from 'next/server';
import { fetchMarketNews, fetchStockNews } from '@/lib/connectors/real-time-finance';
import { generateMockMarketNews, generateMockStockNews } from '@/lib/mock/market-news';

/**
 * API route for fetching market news or stock-specific news
 * GET /api/news?ticker=AAPL (optional)
 */
export async function GET(request: Request) {
  // Extract ticker parameter from URL
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker');
  const language = searchParams.get('language') || 'en';
  
  try {
    console.log(`Fetching news for ${ticker || 'market'} with language ${language}`);
    
    let news;
    let usedMockData = false;
    
    // Check if API keys are available
    const apiKeyAvailable = !!(process.env.RAPIDAPI_KEY || process.env.NEXT_PUBLIC_RAPIDAPI_KEY);
    
    if (apiKeyAvailable) {
      try {
        // Attempt to fetch real data
        news = ticker 
          ? await fetchStockNews(ticker, language as string)
          : await fetchMarketNews(language as string);
          
        console.log(`Successfully fetched ${news.length} news items from API`);
      } catch (apiError) {
        console.warn(`API call failed, falling back to mock data:`, apiError);
        // Fall back to mock data if the API call fails
        usedMockData = true;
        news = ticker 
          ? generateMockStockNews(ticker)
          : generateMockMarketNews();
      }
    } else {
      console.log('RapidAPI Key is missing, using mock data');
      usedMockData = true;
      news = ticker 
        ? generateMockStockNews(ticker)
        : generateMockMarketNews();
    }
    
    // Return the news data
    return NextResponse.json({
      ticker: ticker || 'MARKET',
      news,
      source: usedMockData ? 'mock' : 'api'
    });
  } catch (error) {
    console.error(`Error in news API route:`, error);
    
    // Generate mock data as a last resort
    try {
      const mockNews = ticker 
        ? generateMockStockNews(ticker)
        : generateMockMarketNews();
      
      console.log(`Returning mock data after error`);
      
      return NextResponse.json({
        ticker: ticker || 'MARKET',
        news: mockNews,
        source: 'mock',
        warning: 'An error occurred with the primary data source'
      });
    } catch (mockError) {
      // If even mock data generation fails, return an error
      return NextResponse.json(
        { 
          error: 'Failed to fetch news data', 
          details: error instanceof Error ? error.message : 'Unknown error',
          ticker: ticker || 'MARKET'
        },
        { status: 500 }
      );
    }
  }
} 