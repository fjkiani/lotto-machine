import { Home, BarChart, LineChart, Newspaper, Brain, TrendingUp } from 'lucide-react';

// Define the sidebar navigation items
const navItems = [
  {
    label: 'Dashboard',
    href: '/dashboard',
    icon: <Home className="h-4 w-4" />,
  },
  {
    label: 'Market Overview',
    href: '/market-overview',
    icon: <BarChart className="h-4 w-4" />,
  },
  {
    label: 'Technical Analysis',
    href: '/technical-analysis',
    icon: <LineChart className="h-4 w-4" />,
  },
  {
    label: 'Market News',
    href: '/market-news',
    icon: <Newspaper className="h-4 w-4" />,
  },
  {
    label: 'AI Analysis',
    href: '/ai-analysis',
    icon: <Brain className="h-4 w-4" />,
  },
  {
    label: 'Options Analysis',
    href: '/options-analysis',
    icon: <TrendingUp className="h-4 w-4" />,
  },
  // More items can be added here
]; 