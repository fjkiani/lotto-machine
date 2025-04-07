import { ReactNode } from 'react';
import Link from 'next/link';
import { Home, BarChart, LineChart, Newspaper, BrainCircuit, Network, TrendingUp } from 'lucide-react';

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="flex min-h-screen bg-gray-100 dark:bg-gray-900">
      {/* Sidebar */}
      <aside className="w-64 bg-white dark:bg-gray-800 shadow-md">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <h1 className="text-xl font-bold">AI Hedge Fund</h1>
        </div>
        <nav className="p-4">
          <ul className="space-y-2">
            <li>
              <Link href="/" className="flex items-center p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                <Home className="h-4 w-4 mr-2" />
                <span>Dashboard</span>
              </Link>
            </li>
            <li>
              <Link href="/market-overview" className="flex items-center p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                <BarChart className="h-4 w-4 mr-2" />
                <span>Market Overview</span>
              </Link>
            </li>
            <li>
              <Link href="/analysis" className="flex items-center p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                <LineChart className="h-4 w-4 mr-2" />
                <span>Technical Analysis</span>
              </Link>
            </li>
            <li>
              <Link href="/market-quotes" className="flex items-center p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                <TrendingUp className="h-4 w-4 mr-2" />
                <span>Market Quotes</span>
              </Link>
            </li>
            <li>
              <Link href="/news" className="flex items-center p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                <Newspaper className="h-4 w-4 mr-2" />
                <span>Market News</span>
              </Link>
            </li>
            <li>
              <Link href="/ai-analysis" className="flex items-center p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                <BrainCircuit className="h-4 w-4 mr-2" />
                <span>AI Analysis</span>
              </Link>
            </li>
            <li>
              <Link href="/agent-analysis" className="flex items-center p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                <Network className="h-4 w-4 mr-2" />
                <span>Agent Analysis</span>
              </Link>
            </li>
          </ul>
        </nav>
      </aside>
      
      {/* Main content */}
      <main className="flex-1 p-8 overflow-auto">
        {children}
      </main>
    </div>
  );
} 