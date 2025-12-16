"""
🏥 PRODUCTION HEALTH REPORT GENERATOR
"""

from ..analysis.production_health import HealthStatus

class HealthReportGenerator:
    """Generates health status reports"""
    
    @staticmethod
    def generate_report(date: str, status: HealthStatus) -> str:
        """Generate comprehensive health report"""
        
        report = []
        report.append("=" * 80)
        report.append(f"🏥 PRODUCTION HEALTH REPORT: {date}")
        report.append("=" * 80)
        report.append("")
        
        # Overall Status
        status_icon = "✅" if status.is_healthy else "❌"
        report.append(f"{status_icon} OVERALL STATUS: {'HEALTHY' if status.is_healthy else 'UNHEALTHY'}")
        report.append("-" * 80)
        report.append("")
        
        # Uptime
        report.append("⏱️  SYSTEM UPTIME:")
        report.append("-" * 80)
        report.append(f"  RTH Coverage: {status.rth_coverage:.1f}%")
        report.append(f"  Uptime: {status.uptime_pct:.1f}%")
        if status.last_activity:
            report.append(f"  Last Activity: {status.last_activity.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Data Freshness
        report.append("📡 DATA FRESHNESS:")
        report.append("-" * 80)
        for source, info in status.data_freshness.items():
            if isinstance(info, dict):
                if info.get('available'):
                    age = info.get('age_hours', 0)
                    stale = info.get('is_stale', False)
                    icon = "❌" if stale else "✅"
                    report.append(f"  {icon} {source}: {age:.1f} hours old")
                else:
                    report.append(f"  ❌ {source}: {info.get('error', 'Not available')}")
            elif isinstance(info, bool):
                icon = "⚠️ " if info else "✅"
                report.append(f"  {icon} {source}: {'Anomaly detected' if info else 'Normal'}")
        report.append("")
        
        # Issues
        report.append("🚨 IDENTIFIED ISSUES:")
        report.append("-" * 80)
        if status.issues:
            for issue in status.issues:
                report.append(f"  {issue}")
        else:
            report.append("  ✅ No issues detected")
        report.append("")
        
        # Recommendations
        report.append("💡 RECOMMENDATIONS:")
        report.append("-" * 80)
        for rec in status.recommendations:
            report.append(f"  {rec}")
        report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)


