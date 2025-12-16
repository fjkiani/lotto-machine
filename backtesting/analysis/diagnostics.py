"""
🔍 PRODUCTION DIAGNOSTICS
Diagnoses why signals did/didn't fire during production runs
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import sqlite3
import json

@dataclass
class DiagnosticResult:
    """Diagnostic analysis result"""
    date: str
    rth_signals: int
    non_rth_signals: int
    data_availability: Dict[str, bool]
    threshold_analysis: Dict[str, any]
    market_conditions: Dict[str, any]
    signal_generation_issues: List[str]
    recommendations: List[str]

class ProductionDiagnostics:
    """Diagnoses production signal generation issues"""
    
    def __init__(self, alerts_db_path: str = "data/alerts_history.db", 
                 dp_db_path: str = "data/dp_learning.db"):
        self.alerts_db_path = alerts_db_path
        self.dp_db_path = dp_db_path
    
    def diagnose_date(self, date: str) -> DiagnosticResult:
        """
        Comprehensive diagnosis for a specific date
        
        Analyzes:
        - Signal timing (RTH vs non-RTH)
        - Data availability
        - Threshold issues
        - Market conditions
        - Signal generation problems
        """
        # Load signals
        alerts = self._load_alerts(date)
        
        # Separate RTH vs non-RTH
        rth_signals = [a for a in alerts if 9 <= a['hour'] < 16]
        non_rth_signals = [a for a in alerts if a['hour'] < 9 or a['hour'] >= 16]
        
        # Check data availability
        data_availability = self._check_data_availability(date)
        
        # Analyze thresholds
        threshold_analysis = self._analyze_thresholds(date, alerts)
        
        # Market conditions
        market_conditions = self._analyze_market_conditions(date)
        
        # Signal generation issues
        issues = self._identify_issues(date, rth_signals, non_rth_signals, data_availability)
        
        # Recommendations
        recommendations = self._generate_recommendations(issues, threshold_analysis, data_availability)
        
        return DiagnosticResult(
            date=date,
            rth_signals=len(rth_signals),
            non_rth_signals=len(non_rth_signals),
            data_availability=data_availability,
            threshold_analysis=threshold_analysis,
            market_conditions=market_conditions,
            signal_generation_issues=issues,
            recommendations=recommendations
        )
    
    def _load_alerts(self, date: str) -> List[Dict]:
        """Load alerts for date"""
        conn = sqlite3.connect(self.alerts_db_path)
        cursor = conn.cursor()
        
        start = f"{date}T00:00:00"
        end = f"{date}T23:59:59.999999"
        
        cursor.execute('''
            SELECT timestamp, alert_type, symbol, source, title, embed_json
            FROM alerts
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        ''', [start, end])
        
        alerts = []
        for row in cursor.fetchall():
            try:
                timestamp = datetime.fromisoformat(row[0])
                alerts.append({
                    'timestamp': timestamp,
                    'hour': timestamp.hour,
                    'alert_type': row[1],
                    'symbol': row[2],
                    'source': row[3],
                    'title': row[4],
                    'embed': json.loads(row[5]) if row[5] else {}
                })
            except:
                continue
        
        conn.close()
        return alerts
    
    def _check_data_availability(self, date: str) -> Dict[str, bool]:
        """Check if data sources were available"""
        availability = {
            'dp_data': False,
            'price_data': False,
            'fed_data': False,
            'economic_data': False,
            'details': {}
        }
        
        # Try to check actual API availability
        try:
            from .data_checker import DataAvailabilityChecker
            checker = DataAvailabilityChecker()
            api_checks = checker.check_all_sources(date, "SPY")
            
            availability['dp_data'] = api_checks.get('dp_levels', {}).get('available', False) or \
                                     api_checks.get('dp_prints', {}).get('available', False)
            availability['price_data'] = api_checks.get('price_data', {}).get('available', False)
            availability['market_hours'] = api_checks.get('market_hours', {}).get('is_market_day', False)
            availability['details'] = api_checks
        except Exception as e:
            # Fallback to database checks
            pass
        
        # Check DP data in database
        try:
            conn = sqlite3.connect(self.dp_db_path)
            cursor = conn.cursor()
            start = f"{date}T09:30:00"
            end = f"{date}T16:00:00"
            
            cursor.execute('''
                SELECT COUNT(*) FROM dp_interactions
                WHERE timestamp >= ? AND timestamp < ?
            ''', [start, end])
            
            dp_count = cursor.fetchone()[0]
            if dp_count > 0:
                availability['dp_data'] = True
            
            conn.close()
        except:
            pass
        
        # Check alerts for data sources
        conn = sqlite3.connect(self.alerts_db_path)
        cursor = conn.cursor()
        
        start = f"{date}T09:30:00"
        end = f"{date}T16:00:00"
        
        # Check if any DP alerts fired (indicates DP data available)
        cursor.execute('''
            SELECT COUNT(*) FROM alerts
            WHERE timestamp >= ? AND timestamp < ?
            AND alert_type = 'dp_alert'
        ''', [start, end])
        
        dp_alerts = cursor.fetchone()[0]
        if dp_alerts > 0:
            availability['dp_data'] = True
        
        # Check Fed data
        cursor.execute('''
            SELECT COUNT(*) FROM alerts
            WHERE timestamp >= ? AND timestamp < ?
            AND alert_type = 'fed_watch'
        ''', [start, end])
        
        fed_alerts = cursor.fetchone()[0]
        availability['fed_data'] = fed_alerts > 0
        
        # Check Economic data
        cursor.execute('''
            SELECT COUNT(*) FROM alerts
            WHERE timestamp >= ? AND timestamp < ?
            AND (alert_type LIKE '%economic%' OR source LIKE '%economic%')
        ''', [start, end])
        
        econ_alerts = cursor.fetchone()[0]
        availability['economic_data'] = econ_alerts > 0
        
        conn.close()
        
        return availability
    
    def _analyze_thresholds(self, date: str, alerts: List[Dict]) -> Dict[str, any]:
        """Analyze if thresholds are too high"""
        analysis = {
            'synthesis_fired': False,
            'narrative_fired': False,
            'dp_alerts_fired': False,
            'rth_synthesis_count': 0,
            'rth_narrative_count': 0,
            'rth_dp_count': 0,
            'avg_confluence_rth': 0.0,
            'avg_confluence_non_rth': 0.0
        }
        
        rth_alerts = [a for a in alerts if 9 <= a['hour'] < 16]
        non_rth_alerts = [a for a in alerts if a['hour'] < 9 or a['hour'] >= 16]
        
        # Count RTH signals
        for alert in rth_alerts:
            if alert['alert_type'] == 'synthesis':
                analysis['synthesis_fired'] = True
                analysis['rth_synthesis_count'] += 1
            elif alert['alert_type'] == 'narrative_brain':
                analysis['narrative_fired'] = True
                analysis['rth_narrative_count'] += 1
            elif alert['alert_type'] == 'dp_alert':
                analysis['dp_alerts_fired'] = True
                analysis['rth_dp_count'] += 1
        
        # Calculate confluence (if available in embeds)
        rth_confluences = []
        non_rth_confluences = []
        
        for alert in rth_alerts:
            conf = self._extract_confluence(alert['embed'], alert['title'])
            if conf:
                rth_confluences.append(conf)
        
        for alert in non_rth_alerts:
            conf = self._extract_confluence(alert['embed'], alert['title'])
            if conf:
                non_rth_confluences.append(conf)
        
        if rth_confluences:
            analysis['avg_confluence_rth'] = sum(rth_confluences) / len(rth_confluences)
        if non_rth_confluences:
            analysis['avg_confluence_non_rth'] = sum(non_rth_confluences) / len(non_rth_confluences)
        
        return analysis
    
    def _analyze_market_conditions(self, date: str) -> Dict[str, any]:
        """Analyze market conditions during RTH"""
        conditions = {
            'rth_signals_per_hour': 0.0,
            'peak_hour': None,
            'signal_distribution': {},
            'volatility_estimate': 'UNKNOWN'
        }
        
        # Load RTH alerts
        alerts = self._load_alerts(date)
        rth_alerts = [a for a in alerts if 9 <= a['hour'] < 16]
        
        if not rth_alerts:
            return conditions
        
        # Calculate signals per hour
        hours_active = len(set(a['hour'] for a in rth_alerts))
        if hours_active > 0:
            conditions['rth_signals_per_hour'] = len(rth_alerts) / hours_active
        
        # Find peak hour
        hour_counts = {}
        for alert in rth_alerts:
            hour_counts[alert['hour']] = hour_counts.get(alert['hour'], 0) + 1
        
        if hour_counts:
            peak_hour = max(hour_counts.items(), key=lambda x: x[1])
            conditions['peak_hour'] = peak_hour[0]
            conditions['signal_distribution'] = hour_counts
        
        return conditions
    
    def _identify_issues(self, date: str, rth_signals: List[Dict], 
                         non_rth_signals: List[Dict], 
                         data_availability: Dict[str, bool]) -> List[str]:
        """Identify specific issues"""
        issues = []
        
        # No RTH signals
        if len(rth_signals) == 0:
            issues.append("❌ NO SIGNALS DURING RTH (9:30 AM - 4:00 PM)")
            
            # But signals fired outside RTH
            if len(non_rth_signals) > 0:
                issues.append(f"⚠️  {len(non_rth_signals)} signals fired OUTSIDE market hours")
                issues.append("   → System running but not generating RTH signals")
        
        # Data availability issues
        if not data_availability.get('dp_data'):
            issues.append("❌ NO DP DATA AVAILABLE during RTH")
            issues.append("   → Check API connectivity, rate limits, data freshness")
        
        # Threshold issues
        if len(rth_signals) == 0 and len(non_rth_signals) > 0:
            issues.append("⚠️  Thresholds may be too high for RTH conditions")
            issues.append("   → Non-RTH signals suggest system is working")
        
        # Unified mode issues
        dp_alerts_rth = [s for s in rth_signals if s['alert_type'] == 'dp_alert']
        synthesis_rth = [s for s in rth_signals if s['alert_type'] == 'synthesis']
        
        if len(dp_alerts_rth) > 10 and len(synthesis_rth) == 0:
            issues.append("❌ UNIFIED MODE NOT WORKING")
            issues.append(f"   → {len(dp_alerts_rth)} individual DP alerts sent (should be suppressed)")
        
        # Signal quality issues
        if len(rth_signals) > 0:
            synthesis_count = len([s for s in rth_signals if s['alert_type'] == 'synthesis'])
            narrative_count = len([s for s in rth_signals if s['alert_type'] == 'narrative_brain'])
            
            if synthesis_count == 0 and narrative_count == 0:
                issues.append("⚠️  Only low-quality signals fired (no synthesis/narrative)")
        
        return issues
    
    def _generate_recommendations(self, issues: List[str], 
                                  threshold_analysis: Dict[str, any],
                                  data_availability: Dict[str, bool]) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if "NO SIGNALS DURING RTH" in str(issues):
            recommendations.append("🔧 CHECK DATA SOURCES:")
            recommendations.append("   1. Verify DP API is returning data for current date")
            recommendations.append("   2. Check API rate limits haven't been hit")
            recommendations.append("   3. Verify market hours detection is working")
            recommendations.append("   4. Check if DP levels exist for SPY/QQQ today")
        
        if "NO DP DATA AVAILABLE" in str(issues):
            recommendations.append("🔧 FIX DATA AVAILABILITY:")
            recommendations.append("   1. Test DP API manually: python3 -c 'from core.data.ultimate_chartexchange_client import *; print(get_dark_pool_levels(\"SPY\"))'")
            recommendations.append("   2. Check API key is valid and not expired")
            recommendations.append("   3. Verify date format matches API expectations")
            recommendations.append("   4. Check if data is T+1 delayed (use yesterday's date)")
        
        if "UNIFIED MODE NOT WORKING" in str(issues):
            recommendations.append("🔧 FIX UNIFIED MODE:")
            recommendations.append("   1. Verify unified_mode flag is True in run_all_monitors.py")
            recommendations.append("   2. Check DP alert suppression logic")
            recommendations.append("   3. Verify synthesis is triggering correctly")
        
        if threshold_analysis.get('rth_synthesis_count', 0) == 0:
            recommendations.append("🔧 LOWER THRESHOLDS:")
            recommendations.append("   1. Reduce synthesis confluence threshold (currently 60%+)")
            recommendations.append("   2. Reduce narrative brain threshold (currently 70%+)")
            recommendations.append("   3. Check if DP alerts are being buffered correctly")
        
        if not recommendations:
            recommendations.append("✅ No major issues detected")
            recommendations.append("   → System appears to be working correctly")
        
        return recommendations
    
    @staticmethod
    def _extract_confluence(embed: Dict, title: str) -> Optional[float]:
        """Extract confluence score"""
        import re
        
        # Try fields
        fields = embed.get('fields', [])
        for field in fields:
            value = field.get('value', '')
            match = re.search(r'confluence[:\s]+(\d+(?:\.\d+)?)', value, re.IGNORECASE)
            if match:
                return float(match.group(1))
        
        # Try title
        match = re.search(r'(\d+(?:\.\d+)?)%', title)
        if match:
            return float(match.group(1))
        
        return None

