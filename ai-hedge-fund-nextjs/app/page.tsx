import Link from 'next/link';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="z-10 max-w-5xl w-full items-center justify-center font-mono text-sm">
        <h1 className="text-4xl font-bold mb-8 text-center">
          AI Hedge Fund - Trading Analysis Dashboard
        </h1>
        
        <p className="text-xl mb-8 text-center">
          Welcome to the Next.js version of AI Hedge Fund, providing AI-powered trading insights
          using options data, technical analysis, and market trends.
        </p>
        
        <div className="flex flex-col items-center justify-center gap-4 mt-12">
          <Link 
            href="/dashboard" 
            className="button-primary text-lg px-8 py-3"
          >
            Go to Dashboard
          </Link>
          
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-2xl">
            <Link href="/market-overview" className="card hover:shadow-lg transition">
              <h2 className="text-xl font-semibold">Market Overview</h2>
              <p>View current market data and trends</p>
            </Link>
            
            <Link href="/technical-analysis" className="card hover:shadow-lg transition">
              <h2 className="text-xl font-semibold">Technical Analysis</h2>
              <p>AI-powered technical indicators analysis</p>
            </Link>
            
            <Link href="/options-analysis" className="card hover:shadow-lg transition">
              <h2 className="text-xl font-semibold">Options Analysis</h2>
              <p>Options data and trading strategy recommendations</p>
            </Link>
            
            <Link href="/memory-analysis" className="card hover:shadow-lg transition">
              <h2 className="text-xl font-semibold">Memory Analysis</h2>
              <p>Enhanced analysis with historical context</p>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
} 