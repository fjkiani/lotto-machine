'use client';

import { Recommendation, AnalystReport } from '@/lib/connectors/yahoo-finance-insights';

interface AnalystRecommendationsProps {
  recommendation: Recommendation;
  reports?: AnalystReport[];
}

export default function AnalystRecommendations({ recommendation, reports = [] }: AnalystRecommendationsProps) {
  // Function to format date
  const formatDate = (dateString: string) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    });
  };
  
  // Function to determine rating color
  const getRatingColor = (rating: string) => {
    if (!rating) return 'text-gray-500';
    
    const lowerCaseRating = rating.toLowerCase();
    if (lowerCaseRating.includes('buy') || lowerCaseRating.includes('outperform') || lowerCaseRating.includes('strong')) {
      return 'text-success-600';
    } else if (lowerCaseRating.includes('sell') || lowerCaseRating.includes('underperform')) {
      return 'text-danger-600';
    } else {
      return 'text-warning-600'; // Hold, Neutral, etc.
    }
  };
  
  return (
    <div className="space-y-6">
      {/* Latest Recommendation */}
      {recommendation && recommendation.provider && (
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Latest Recommendation</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Provider</p>
              <p className="font-medium">{recommendation.provider}</p>
            </div>
            
            <div>
              <p className="text-sm text-gray-500">Rating</p>
              <p className={`font-medium ${getRatingColor(recommendation.rating as string)}`}>
                {recommendation.rating || 'N/A'}
              </p>
            </div>
            
            <div>
              <p className="text-sm text-gray-500">Target Price</p>
              <p className="font-medium">
                {recommendation.targetPrice ? `$${recommendation.targetPrice}` : 'N/A'}
              </p>
            </div>
          </div>
        </div>
      )}
      
      {/* Recent Reports */}
      {reports && reports.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold mb-4">Recent Analyst Reports</h3>
          <div className="space-y-4">
            {reports.map((report, index) => (
              <div key={index} className="pb-4 border-b border-gray-200 dark:border-gray-700 last:border-0">
                <div className="flex justify-between items-start">
                  <div className="font-medium">{report.provider}</div>
                </div>
                
                <div className="mt-1 text-sm">{report.title}</div>
                
                <div className="mt-2 flex justify-between items-center text-sm text-gray-500">
                  <div>{formatDate(report.publishedOn)}</div>
                </div>
                
                {report.summary && (
                  <div className="mt-2 text-xs text-gray-600">
                    {report.summary.length > 150 ? `${report.summary.substring(0, 150)}...` : report.summary}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
} 