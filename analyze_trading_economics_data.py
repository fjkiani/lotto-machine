#!/usr/bin/env python3
"""
Analyze Trading Economics Data Quality and Structure
======================================================

Comprehensive analysis of the MCP server data to understand:
- Data quality and completeness
- Parsing accuracy
- Date/time handling
- Country/event mapping
- Potential for exploitation
"""

import json
import asyncio
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Dict, List, Any

# Import the MCP client
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'trading-Economics', 'trading_economics_calendar_mcp-main'))

from trading_economics_calendar.client import fetch_calendar_events, TradingEconomicsClient


class DataAnalyzer:
    """Analyze Trading Economics data quality and structure"""

    def __init__(self):
        self.client = TradingEconomicsClient()

    def analyze_date_parsing(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze date parsing quality"""
        dates = [event.get('date') for event in events if event.get('date')]
        date_counter = Counter(dates)

        # Check for date parsing issues
        current_date = datetime.now().strftime('%Y-%m-%d')
        future_dates = [d for d in dates if d > current_date]

        return {
            'total_events': len(events),
            'unique_dates': len(date_counter),
            'most_common_date': date_counter.most_common(1)[0] if date_counter else None,
            'date_range': {
                'earliest': min(dates) if dates else None,
                'latest': max(dates) if dates else None
            },
            'future_dates': len(future_dates),
            'current_date_default': current_date in date_counter,
            'date_distribution': dict(date_counter.most_common(10))
        }

    def analyze_country_parsing(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze country field parsing"""
        countries = [event.get('country') for event in events if event.get('country')]
        country_counter = Counter(countries)

        # Identify parsing issues
        short_codes = [c for c in countries if len(c) <= 3]  # Likely parsing errors
        actual_countries = [c for c in countries if len(c) > 3]

        # Check against known major countries
        major_countries = set(self.client.MAJOR_COUNTRIES.values())
        recognized_countries = [c for c in countries if c in major_countries]

        return {
            'total_events': len(events),
            'unique_countries': len(country_counter),
            'short_codes': len(short_codes),  # Likely parsing errors
            'actual_countries': len(actual_countries),
            'recognized_countries': len(recognized_countries),
            'unrecognized_countries': len(country_counter) - len(recognized_countries),
            'country_distribution': dict(country_counter.most_common(10)),
            'parsing_error_rate': len(short_codes) / len(countries) if countries else 0
        }

    def analyze_importance_levels(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze importance level distribution"""
        importance_levels = [event.get('importance', 0) for event in events]
        importance_counter = Counter(importance_levels)

        # Check if filtering worked
        high_importance = [e for e in events if e.get('importance', 0) >= 3]
        requested_high = len([e for e in events if e.get('importance', 0) == 3])

        return {
            'importance_distribution': dict(importance_counter),
            'high_importance_events': len(high_importance),
            'explicitly_high_events': requested_high,
            'filtering_accuracy': requested_high / len(high_importance) if high_importance else 0
        }

    def analyze_event_names(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze event name quality"""
        event_names = [event.get('event', '') for event in events if event.get('event')]
        event_counter = Counter(event_names)

        # Identify parsing issues
        short_events = [e for e in event_names if len(e) <= 3]  # Likely parsing errors
        actual_events = [e for e in event_names if len(e) > 3]

        # Categorize events
        economic_indicators = []
        central_bank_events = []
        other_events = []

        for event in actual_events:
            event_lower = event.lower()
            if any(term in event_lower for term in ['inflation', 'gdp', 'employment', 'unemployment', 'retail', 'pmi', 'confidence']):
                economic_indicators.append(event)
            elif any(term in event_lower for term in ['fed', 'ecb', 'boe', 'boj', 'boc', 'interest rate', 'press conference']):
                central_bank_events.append(event)
            else:
                other_events.append(event)

        return {
            'total_events': len(events),
            'unique_event_names': len(event_counter),
            'parsing_errors': len(short_events),
            'valid_events': len(actual_events),
            'economic_indicators': len(economic_indicators),
            'central_bank_events': len(central_bank_events),
            'other_events': len(other_events),
            'top_events': dict(event_counter.most_common(10)),
            'sample_events': actual_events[:20]  # First 20 valid events
        }

    def analyze_time_parsing(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze time field parsing"""
        times = [event.get('time', '') for event in events if event.get('time')]

        # Categorize time formats
        proper_times = []
        date_strings = []
        invalid_times = []

        for time_str in times:
            if ':' in time_str and ('AM' in time_str or 'PM' in time_str):
                proper_times.append(time_str)
            elif ' ' in time_str and any(month in time_str for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                date_strings.append(time_str)
            else:
                invalid_times.append(time_str)

        return {
            'total_times': len(times),
            'proper_times': len(proper_times),
            'date_strings': len(date_strings),
            'invalid_times': len(invalid_times),
            'parsing_accuracy': len(proper_times) / len(times) if times else 0,
            'sample_proper_times': proper_times[:5],
            'sample_date_strings': date_strings[:5]
        }

    def analyze_economic_data_quality(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze actual/forecast/previous data quality"""
        events_with_actual = [e for e in events if e.get('actual')]
        events_with_forecast = [e for e in events if e.get('forecast')]
        events_with_previous = [e for e in events if e.get('previous')]

        # Check data completeness
        complete_data = [e for e in events if all(e.get(field) for field in ['actual', 'forecast', 'previous'])]

        # Try to identify surprise opportunities
        surprises = []
        for event in complete_data:
            try:
                actual = self._parse_value(event['actual'])
                forecast = self._parse_value(event['forecast'])
                if actual is not None and forecast is not None:
                    surprise = actual - forecast
                    surprise_pct = abs(surprise / forecast) if forecast != 0 else 0
                    if surprise_pct > 0.01:  # >1% surprise
                        surprises.append({
                            'event': event.get('event'),
                            'country': event.get('country'),
                            'surprise': surprise,
                            'surprise_pct': surprise_pct
                        })
            except:
                continue

        return {
            'total_events': len(events),
            'with_actual': len(events_with_actual),
            'with_forecast': len(events_with_forecast),
            'with_previous': len(events_with_previous),
            'complete_triplets': len(complete_data),
            'data_completeness': len(complete_data) / len(events) if events else 0,
            'potential_surprises': len(surprises),
            'sample_surprises': surprises[:5]
        }

    def _parse_value(self, value_str: str) -> float:
        """Parse economic value strings to float"""
        if not value_str:
            return None
        try:
            # Remove common suffixes and clean
            cleaned = value_str.replace('%', '').replace(',', '').replace('$', '').strip()
            return float(cleaned)
        except:
            return None

    def generate_exploitation_report(self, events: List[Dict]) -> Dict[str, Any]:
        """Generate comprehensive exploitation analysis"""

        # Analyze all aspects
        date_analysis = self.analyze_date_parsing(events)
        country_analysis = self.analyze_country_parsing(events)
        importance_analysis = self.analyze_importance_levels(events)
        event_analysis = self.analyze_event_names(events)
        time_analysis = self.analyze_time_parsing(events)
        data_quality = self.analyze_economic_data_quality(events)

        # Overall data quality score (0-100)
        quality_score = self._calculate_quality_score(
            date_analysis, country_analysis, time_analysis, data_quality
        )

        # Exploitation opportunities
        opportunities = self._identify_exploitation_opportunities(
            date_analysis, country_analysis, event_analysis, data_quality
        )

        return {
            'timestamp': datetime.now().isoformat(),
            'data_quality_score': quality_score,
            'total_events': len(events),
            'analysis': {
                'dates': date_analysis,
                'countries': country_analysis,
                'importance': importance_analysis,
                'events': event_analysis,
                'times': time_analysis,
                'economic_data': data_quality
            },
            'exploitation_opportunities': opportunities,
            'recommendations': self._generate_recommendations(quality_score, opportunities)
        }

    def _calculate_quality_score(self, dates, countries, times, data_quality) -> float:
        """Calculate overall data quality score (0-100)"""
        scores = []

        # Date parsing quality (30%)
        if dates['total_events'] > 0:
            future_date_penalty = min(dates['future_dates'] / dates['total_events'], 0.5)  # Max 50% penalty
            date_score = (1 - future_date_penalty) * 30
            scores.append(date_score)

        # Country parsing quality (25%)
        if countries['total_events'] > 0:
            parsing_accuracy = 1 - countries['parsing_error_rate']
            recognition_rate = countries['recognized_countries'] / countries['unique_countries'] if countries['unique_countries'] > 0 else 0
            country_score = (parsing_accuracy * 0.7 + recognition_rate * 0.3) * 25
            scores.append(country_score)

        # Time parsing quality (20%)
        time_score = times['parsing_accuracy'] * 20
        scores.append(time_score)

        # Economic data completeness (25%)
        data_score = data_quality['data_completeness'] * 25
        scores.append(data_score)

        return sum(scores)

    def _identify_exploitation_opportunities(self, dates, countries, events, data_quality):
        """Identify specific exploitation opportunities"""

        opportunities = []

        # High-frequency economic data
        if events['economic_indicators'] > 20:
            opportunities.append({
                'type': 'high_frequency_economic_data',
                'description': f"{events['economic_indicators']} economic indicators available for correlation analysis",
                'exploitation': 'Build economic surprise prediction models',
                'potential_value': 'HIGH'
            })

        # Central bank events
        if events['central_bank_events'] > 5:
            opportunities.append({
                'type': 'central_bank_events',
                'description': f"{events['central_bank_events']} central bank events for volatility trading",
                'exploitation': 'Position before Fed/ECB/BoE announcements',
                'potential_value': 'VERY HIGH'
            })

        # Surprise opportunities
        if data_quality['potential_surprises'] > 0:
            opportunities.append({
                'type': 'economic_surprises',
                'description': f"{data_quality['potential_surprises']} events with actual vs forecast data",
                'exploitation': 'Trade economic surprises in real-time',
                'potential_value': 'HIGH'
            })

        # US data focus
        us_events = [e for e in countries.get('country_distribution', {}) if e.get('country') == 'United States']
        if us_events:
            opportunities.append({
                'type': 'us_economic_focus',
                'description': 'US economic data has highest market impact',
                'exploitation': 'Prioritize US events for trading signals',
                'potential_value': 'HIGH'
            })

        return opportunities

    def _generate_recommendations(self, quality_score: float, opportunities):
        """Generate actionable recommendations"""

        recommendations = []

        if quality_score < 50:
            recommendations.append({
                'priority': 'CRITICAL',
                'action': 'Fix HTML parsing - current parser is broken',
                'impact': 'Data unusable in current state'
            })

        elif quality_score < 70:
            recommendations.append({
                'priority': 'HIGH',
                'action': 'Improve date and country parsing accuracy',
                'impact': 'Better event timing and filtering'
            })

        if opportunities:
            recommendations.append({
                'priority': 'MEDIUM',
                'action': 'Integrate with trading system for real-time alerts',
                'impact': 'Automated volatility and surprise trading'
            })

        if len(opportunities) > 2:
            recommendations.append({
                'priority': 'MEDIUM',
                'action': 'Build economic surprise prediction models',
                'impact': 'Predictive trading edge'
            })

        return recommendations


async def main():
    """Main analysis function"""
    print("🔥 TRADING ECONOMICS DATA QUALITY ANALYSIS")
    print("=" * 60)

    analyzer = DataAnalyzer()

    # Test different queries
    test_queries = [
        {
            'name': 'This Week High Impact',
            'params': {'importance': 'high'}
        },
        {
            'name': 'US Events This Week',
            'params': {'countries': ['United States']}
        },
        {
            'name': 'European Events',
            'params': {'countries': ['Germany', 'France', 'United Kingdom']}
        },
        {
            'name': 'Central Bank Events',
            'params': {'importance': 'high'}
        }
    ]

    all_results = {}

    for query in test_queries:
        print(f"\n📊 Testing: {query['name']}")
        print("-" * 40)

        try:
            # Fetch data
            events = await fetch_calendar_events(**query['params'])
            print(f"✅ Found {len(events)} events")

            # Analyze
            analysis = analyzer.generate_exploitation_report(events)

            # Display key metrics
            quality = analysis['data_quality_score']
            quality_color = "🔴" if quality < 50 else "🟡" if quality < 70 else "🟢"
            print(f"🎯 Data Quality Score: {quality_color} {quality:.1f}/100")

            # Show exploitation opportunities
            opportunities = analysis['exploitation_opportunities']
            if opportunities:
                print(f"💰 Exploitation Opportunities: {len(opportunities)}")
                for opp in opportunities[:2]:  # Show top 2
                    print(f"  • {opp['type'].replace('_', ' ').title()}: {opp['potential_value']}")

            # Store results
            all_results[query['name']] = analysis

        except Exception as e:
            print(f"❌ Error: {e}")
            all_results[query['name']] = {'error': str(e)}

    # Overall assessment
    print("\n" + "=" * 60)
    print("🎯 OVERALL ASSESSMENT")
    print("=" * 60)

    # Calculate average quality
    successful_analyses = [r for r in all_results.values() if isinstance(r, dict) and 'data_quality_score' in r]
    if successful_analyses:
        avg_quality = sum(r['data_quality_score'] for r in successful_analyses) / len(successful_analyses)
        quality_assessment = "🔴 POOR" if avg_quality < 50 else "🟡 FAIR" if avg_quality < 70 else "🟢 GOOD"
        print(f"Average Data Quality: {quality_assessment} ({avg_quality:.1f}/100)")

        total_opportunities = sum(len(r.get('exploitation_opportunities', [])) for r in successful_analyses)
        print(f"Total Exploitation Opportunities Identified: {total_opportunities}")

        # Show top recommendations
        all_recommendations = []
        for analysis in successful_analyses:
            all_recommendations.extend(analysis.get('recommendations', []))

        if all_recommendations:
            print("\n🔧 KEY RECOMMENDATIONS:")
            # Deduplicate and show top 3
            seen = set()
            for rec in all_recommendations:
                key = (rec['priority'], rec['action'])
                if key not in seen:
                    print(f"  {rec['priority']}: {rec['action']}")
                    seen.add(key)
                    if len(seen) >= 3:
                        break

    print("\n💡 CONCLUSION:")
    print("The Trading Economics MCP provides valuable economic calendar data,")
    print("but requires significant parsing improvements before production use.")
    print("High potential for volatility trading and economic surprise strategies.")

    # Save detailed analysis
    output_file = f"trading_economics_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n📄 Detailed analysis saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())



