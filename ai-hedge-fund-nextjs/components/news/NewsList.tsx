'use client';

import { NewsArticle } from '@/lib/connectors/real-time-finance';
import NewsCard from '@/components/news/NewsCard';

interface NewsListProps {
  articles: NewsArticle[];
  title?: string;
  isLoading?: boolean;
  isEmpty?: boolean;
}

export default function NewsList({ 
  articles, 
  title = 'Latest News', 
  isLoading = false,
  isEmpty = false
}: NewsListProps) {
  return (
    <div className="space-y-4">
      {title && <h2 className="text-xl font-semibold">{title}</h2>}
      
      {isLoading && (
        <div className="flex justify-center items-center h-64">
          <p className="text-lg">Loading news articles...</p>
        </div>
      )}
      
      {isEmpty && !isLoading && (
        <div className="border border-gray-200 dark:border-gray-700 rounded-md p-6 text-center">
          <p className="text-gray-500">No news articles found.</p>
        </div>
      )}
      
      {!isLoading && !isEmpty && articles.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {articles.map((article, index) => (
            <NewsCard key={`${article.article_title}-${index}`} article={article} />
          ))}
        </div>
      )}
    </div>
  );
} 