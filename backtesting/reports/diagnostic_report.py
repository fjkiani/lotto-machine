"""
📊 DIAGNOSTIC REPORT GENERATOR
Generates production debugging reports
"""

from ..analysis.diagnostics import DiagnosticResult

class DiagnosticReportGenerator:
    """Generates diagnostic reports"""
    
    @staticmethod
    def generate_report(result: DiagnosticResult) -> str:
        """Generate comprehensive diagnostic report"""
        
        report = []
        report.append("=" * 80)
        report.append(f"🔍 PRODUCTION DIAGNOSTICS: {result.date}")
        report.append("=" * 80)
        report.append("")
        
        # Signal Summary
        report.append("📊 SIGNAL SUMMARY:")
        report.append("-" * 80)
        report.append(f"  RTH Signals (9:30 AM - 4:00 PM): {result.rth_signals}")
        report.append(f"  Non-RTH Signals: {result.non_rth_signals}")
        report.append(f"  Total Signals: {result.rth_signals + result.non_rth_signals}")
        report.append("")
        
        if result.rth_signals == 0:
            report.append("  ⚠️  CRITICAL: NO SIGNALS DURING MARKET HOURS!")
            report.append("")
        
        # Data Availability
        report.append("📡 DATA AVAILABILITY:")
        report.append("-" * 80)
        for source, available in result.data_availability.items():
            if source == 'details':
                continue
            status = "✅" if available else "❌"
            report.append(f"  {status} {source.replace('_', ' ').title()}: {'Available' if available else 'NOT AVAILABLE'}")
        
        # Show detailed API check results if available
        if result.data_availability.get('details'):
            details = result.data_availability['details']
            report.append("")
            report.append("  📊 API Check Details:")
            if details.get('dp_levels'):
                dp = details['dp_levels']
                report.append(f"    DP Levels: {dp.get('count', 0)} found" + (f" ({dp.get('error')})" if dp.get('error') else ""))
            if details.get('dp_prints'):
                dp = details['dp_prints']
                report.append(f"    DP Prints: {dp.get('count', 0)} found" + (f" ({dp.get('error')})" if dp.get('error') else ""))
            if details.get('price_data'):
                price = details['price_data']
                report.append(f"    Price Data: {price.get('count', 0)} bars" + (f" ({price.get('error')})" if price.get('error') else ""))
            if details.get('market_hours'):
                mh = details['market_hours']
                report.append(f"    Market Day: {mh.get('is_market_day', False)} ({mh.get('day_of_week', 'Unknown')})")
        report.append("")
        
        # Threshold Analysis
        report.append("🎯 THRESHOLD ANALYSIS:")
        report.append("-" * 80)
        ta = result.threshold_analysis
        report.append(f"  Synthesis Fired (RTH): {ta.get('rth_synthesis_count', 0)}")
        report.append(f"  Narrative Brain Fired (RTH): {ta.get('rth_narrative_count', 0)}")
        report.append(f"  DP Alerts Fired (RTH): {ta.get('rth_dp_count', 0)}")
        
        if ta.get('avg_confluence_rth', 0) > 0:
            report.append(f"  Avg Confluence (RTH): {ta['avg_confluence_rth']:.1f}%")
        if ta.get('avg_confluence_non_rth', 0) > 0:
            report.append(f"  Avg Confluence (Non-RTH): {ta['avg_confluence_non_rth']:.1f}%")
        report.append("")
        
        # Market Conditions
        report.append("📈 MARKET CONDITIONS:")
        report.append("-" * 80)
        mc = result.market_conditions
        if mc.get('rth_signals_per_hour', 0) > 0:
            report.append(f"  Signals per Hour (RTH): {mc['rth_signals_per_hour']:.1f}")
        if mc.get('peak_hour'):
            report.append(f"  Peak Hour: {mc['peak_hour']:02d}:00")
        
        if mc.get('signal_distribution'):
            report.append("  Signal Distribution by Hour:")
            for hour in sorted(mc['signal_distribution'].keys()):
                count = mc['signal_distribution'][hour]
                report.append(f"    {hour:02d}:00 - {hour+1:02d}:00: {count:3d} signals")
        report.append("")
        
        # Issues
        report.append("🚨 IDENTIFIED ISSUES:")
        report.append("-" * 80)
        if result.signal_generation_issues:
            for issue in result.signal_generation_issues:
                report.append(f"  {issue}")
        else:
            report.append("  ✅ No issues detected")
        report.append("")
        
        # Recommendations
        report.append("💡 RECOMMENDATIONS:")
        report.append("-" * 80)
        for rec in result.recommendations:
            report.append(f"  {rec}")
        report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)

