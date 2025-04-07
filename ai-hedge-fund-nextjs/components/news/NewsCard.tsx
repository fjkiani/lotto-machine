'use client';

import { NewsArticle } from '@/lib/connectors/real-time-finance';
import Image from 'next/image';

interface NewsCardProps {
  article: NewsArticle;
}

export default function NewsCard({ article }: NewsCardProps) {
  // Format the publication date
  const formatDate = (dateString: string) => {
    if (!dateString) return 'N/A';
    
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateString;
    }
  };
  
  // Handle clicking on the news article
  const handleArticleClick = () => {
    if (article.article_url) {
      window.open(article.article_url, '_blank', 'noopener,noreferrer');
    }
  };
  
  return (
    <div 
      className="card p-4 hover:shadow-md transition-shadow cursor-pointer flex flex-col space-y-4"
      onClick={handleArticleClick}
    >
      {/* Article Image (if available) */}
      {article.article_photo_url && (
        <div className="w-full h-40 relative rounded-md overflow-hidden">
          <Image
            src={article.article_photo_url}
            alt={article.article_title}
            fill
            sizes="(max-width: 768px) 100vw, 33vw"
            style={{ objectFit: 'cover' }}
            onError={(e) => {
              // Replace broken images with a placeholder
              (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x200?text=No+Image';
            }}
          />
        </div>
      )}
      
      {/* Article Title */}
      <h3 className="text-lg font-medium leading-tight">
        {article.article_title}
      </h3>
      
      {/* Source and Date */}
      <div className="flex justify-between items-center mt-auto text-sm text-gray-500">
        <span className="font-medium">{article.source}</span>
        <span>{formatDate(article.post_time_utc)}</span>
      </div>
    </div>
  );
} 