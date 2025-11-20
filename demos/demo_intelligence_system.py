#!/usr/bin/env python3
"""
Alpha's Real-Time Intelligence System Demo
Demonstrates the complete intelligence gathering pipeline

This implements Alpha's blueprint:
Data Feeds → Ingestion → Analytics → Narrative → Alerts → Feedback
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.intelligence.realtime_system import RealTimeIntelligenceSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def demo_intelligence_system():
    """Demo the complete intelligence system"""
    try:
        logger.info("🚀 Starting Alpha's Real-Time Intelligence System Demo")
        
        # Configuration
        config = {
            'polling_interval': 30,  # 30 seconds for demo
            'monitored_tickers': ['SPY', 'QQQ', 'AAPL', 'TSLA'],
            
            # Data feeds configuration
            'feeds': {
                'tavily_api_key': None,  # Set your API key
                'twitter_bearer_token': None,  # Set your token
                'brokers': {
                    'alpaca': {
                        'api_key': None,  # Set your API key
                        'secret_key': None,  # Set your secret
                        'base_url': 'https://paper-api.alpaca.markets'
                    }
                }
            },
            
            # Analytics configuration
            'analytics': {
                'trade_size_threshold': 5.0,
                'price_zscore_threshold': 2.0,
                'volume_zscore_threshold': 2.0,
                'options_sweep_threshold': 1000,
                'dark_pool_threshold': 0.4,
                'cluster_window_minutes': 5,
                'min_anomalies_cluster': 2
            },
            
            # Narrative configuration
            'narrative': {
                'llm_provider': 'gemini',
                'llm_model': 'gemini-1.5-flash',
                'batch_interval_minutes': 3
            },
            
            # Alerts configuration
            'alerts': {
                'dashboard_alerts': True,
                'sms_alerts': False,
                'telegram_alerts': False,
                'email_alerts': False,
                'webhook_alerts': False,
                'database_logging': True,
                'critical_threshold': 0.9,
                'high_threshold': 0.7,
                'medium_threshold': 0.5,
                'low_threshold': 0.3
            },
            
            # Feedback configuration
            'feedback': {
                'learning_rate': 0.1,
                'min_samples': 10,
                'feedback_window_days': 7,
                'max_threshold_adjustment': 0.2
            }
        }
        
        # Initialize system
        intelligence_system = RealTimeIntelligenceSystem(config)
        
        # Start the system
        logger.info("Starting intelligence system...")
        await intelligence_system.start_system()
        
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo error: {e}")
    finally:
        logger.info("Demo completed")

async def demo_single_cycle():
    """Demo a single intelligence cycle"""
    try:
        logger.info("🔄 Running Single Intelligence Cycle Demo")
        
        # Simple config for demo
        config = {
            'polling_interval': 30,
            'monitored_tickers': ['SPY'],
            'feeds': {},
            'analytics': {},
            'narrative': {},
            'alerts': {'dashboard_alerts': True, 'database_logging': True},
            'feedback': {}
        }
        
        # Initialize system
        intelligence_system = RealTimeIntelligenceSystem(config)
        await intelligence_system.initialize()
        
        # Run one cycle
        logger.info("Running single intelligence cycle...")
        
        # 1. Poll all feeds
        await intelligence_system._poll_all_feeds()
        
        # 2. Detect anomalies
        await intelligence_system._detect_anomalies()
        
        # 3. Generate narratives
        await intelligence_system._generate_narratives()
        
        # 4. Cluster anomalies
        await intelligence_system._cluster_anomalies()
        
        # 5. Process alerts
        await intelligence_system._process_alerts()
        
        # 6. Update feedback
        await intelligence_system._update_feedback()
        
        # Show results
        status = intelligence_system.get_system_status()
        logger.info(f"Cycle completed. Status: {status}")
        
        # Cleanup
        await intelligence_system.stop_system()
        
    except Exception as e:
        logger.error(f"Single cycle demo error: {e}")

async def demo_components():
    """Demo individual components"""
    try:
        logger.info("🧩 Running Component Demo")
        
        # Demo Data Feed Manager
        logger.info("Testing Data Feed Manager...")
        from src.intelligence.feeds import DataFeedManager
        
        feed_config = {
            'tavily_api_key': None,
            'twitter_bearer_token': None,
            'brokers': {}
        }
        
        feed_manager = DataFeedManager(feed_config)
        await feed_manager.initialize()
        
        # Test news feeds (will return empty without API keys)
        news = await feed_manager.get_tavily_news(['SPY'])
        logger.info(f"Tavily news results: {len(news)} articles")
        
        rss_news = await feed_manager.get_rss_feeds()
        logger.info(f"RSS news results: {len(rss_news)} articles")
        
        await feed_manager.cleanup()
        
        # Demo Analytics
        logger.info("Testing Real-Time Analytics...")
        from src.intelligence.analytics import RealTimeAnalytics
        
        analytics_config = {
            'trade_size_threshold': 5.0,
            'price_zscore_threshold': 2.0,
            'monitored_tickers': ['SPY']
        }
        
        analytics = RealTimeAnalytics(analytics_config)
        await analytics.initialize()
        
        # Test anomaly detection with mock data
        from src.intelligence.realtime_system import MarketEvent
        
        mock_events = [
            MarketEvent(
                ticker='SPY',
                timestamp=datetime.now(),
                source='broker',
                event_type='trade',
                data={'price': 450.0, 'volume': 1000000, 'size': 50000},
                raw_text='Large trade: 50k shares @ $450'
            )
        ]
        
        anomalies = await analytics.detect_anomalies('SPY', mock_events)
        logger.info(f"Detected {len(anomalies)} anomalies")
        
        await analytics.cleanup()
        
        logger.info("Component demo completed successfully")
        
    except Exception as e:
        logger.error(f"Component demo error: {e}")

def main():
    """Main demo function"""
    print("🎯 Alpha's Real-Time Intelligence System Demo")
    print("=" * 50)
    print("Choose demo mode:")
    print("1. Single Intelligence Cycle")
    print("2. Component Testing")
    print("3. Full System (Continuous)")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == '1':
        asyncio.run(demo_single_cycle())
    elif choice == '2':
        asyncio.run(demo_components())
    elif choice == '3':
        asyncio.run(demo_intelligence_system())
    elif choice == '4':
        print("Exiting...")
    else:
        print("Invalid choice. Exiting...")

if __name__ == "__main__":
    main()
