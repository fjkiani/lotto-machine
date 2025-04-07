import { NextResponse } from 'next/server';
import { fetchMarketTrends, fetchGainersAndLosers } from '@/lib/connectors/real-time-finance';
import { generateMockTrendingStocks } from '@/lib/mock/trending-stocks';

/**
 * API route for fetching market trends
 * GET /api/trends?type=gainers (options: gainers, losers, actives, all)
 */
export async function GET(request: Request) {
  // Extract trend type parameter from URL
  const { searchParams } = new URL(request.url);
  const trendType = searchParams.get('type') || 'all';
  
  try {
    const validTypes = ['gainers', 'losers', 'actives', 'advanced_decline', 'price_volume'];
    let trends;
    let usedMockData = false;
    
    // Check if API keys are available
    const apiKeyAvailable = !!(process.env.RAPIDAPI_KEY || process.env.NEXT_PUBLIC_RAPIDAPI_KEY);
    
    if (apiKeyAvailable) {
      try {
        // Attempt to fetch real data
        if (trendType === 'all') {
          trends = await fetchGainersAndLosers();
        } else if (validTypes.includes(trendType)) {
          trends = {
            type: trendType,
            trends: await fetchMarketTrends(trendType)
          };
        } else {
          return NextResponse.json(
            { error: `Invalid trend type: ${trendType}. Valid options are: ${validTypes.join(', ')} or 'all'` },
            { status: 400 }
          );
        }
        console.log(`Successfully fetched ${trendType} trends from API`);
      } catch (apiError) {
        console.warn(`API call failed, falling back to mock data:`, apiError);
        usedMockData = true;
        trends = generateMockTrendsData(trendType);
      }
    } else {
      console.log('RapidAPI Key is missing, using mock data');
      usedMockData = true;
      trends = generateMockTrendsData(trendType);
    }
    
    // Add metadata about data source
    return NextResponse.json({
      ...trends,
      source: usedMockData ? 'mock' : 'api'
    });
  } catch (error) {
    console.error(`Error in trends API route:`, error);
    
    // Generate mock data as a last resort
    try {
      const mockTrends = generateMockTrendsData(trendType);
      console.log(`Returning mock data after error`);
      
      return NextResponse.json({
        ...mockTrends,
        source: 'mock',
        warning: 'An error occurred with the primary data source'
      });
    } catch (mockError) {
      // If even mock data generation fails, return an error
      return NextResponse.json(
        { error: 'Failed to fetch market trends data' },
        { status: 500 }
      );
    }
  }
}

/**
 * Helper function to generate mock trends data based on the requested type
 */
function generateMockTrendsData(trendType: string) {
  if (trendType === 'all') {
    return {
      gainers: generateMockTrendingStocks('gainers'),
      losers: generateMockTrendingStocks('losers')
    };
  } else if (trendType === 'gainers' || trendType === 'losers' || trendType === 'actives') {
    return {
      type: trendType,
      trends: generateMockTrendingStocks(trendType as 'gainers' | 'losers' | 'active')
    };
  } else {
    // For other trend types, just return empty data
    return {
      type: trendType,
      trends: []
    };
  }
} 