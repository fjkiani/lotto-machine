"""
Trading Date Resolver

Resolves the actual trading date when data is available.
Critical for preventing "asking about today but only having yesterday's data" bugs.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def resolve_trading_date(symbol: str, requested_date: str) -> str:
    """
    Resolve the actual trading date we have data for.
    
    This fixes the bug where we ask for narrative on "today" (calendar)
    but only have prices for the last completed trading session.
    
    Args:
        symbol: Ticker symbol (e.g., 'SPY')
        requested_date: Date string in 'YYYY-MM-DD' format
        
    Returns:
        Trading date string in 'YYYY-MM-DD' format
    """
    try:
        import yfinance as yf
        
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", interval="1d")
        
        if hist.empty:
            logger.warning("No historical data for %s, using requested date", symbol)
            return requested_date
        
        last_trading_date = hist.index[-1].date()
        requested_date_obj = datetime.strptime(requested_date, "%Y-%m-%d").date()
        
        # Use the last trading day if we're before today's close
        if last_trading_date < requested_date_obj:
            resolved = last_trading_date.strftime("%Y-%m-%d")
            logger.info(
                "📅 Resolved trading date: requested=%s → actual=%s",
                requested_date, resolved
            )
            return resolved
        
        return requested_date
        
    except Exception as e:
        logger.error("Error resolving trading date for %s: %s", symbol, e)
        return requested_date


def build_realized_move_header(symbol: str, trading_date: str) -> str:
    """
    Build a deterministic realized move line (close-to-close) header.
    
    This anchors the narrative to actual market performance, not just web text.
    
    Args:
        symbol: Ticker symbol
        trading_date: Trading date string in 'YYYY-MM-DD' format
        
    Returns:
        Header string with realized move, or empty string if unavailable
    """
    try:
        import yfinance as yf
        
        ticker = yf.Ticker(symbol)
        hist_px = ticker.history(period="10d", interval="1d")
        
        if hist_px.empty:
            return ""
        
        target_date = datetime.strptime(trading_date, "%Y-%m-%d").date()
        matching_indices = [
            i for i, dt in enumerate(hist_px.index.date) if dt == target_date
        ]
        
        if not matching_indices:
            return ""
        
        idx = matching_indices[0]
        close_today = float(hist_px["Close"].iloc[idx])
        
        if idx == 0:
            # No previous day available
            return f"{symbol} closed at ${close_today:.2f} on {trading_date}.\n\n"
        
        close_prev = float(hist_px["Close"].iloc[idx - 1])
        pct_change = (close_today / close_prev - 1.0) * 100.0
        
        direction = "UP" if pct_change > 0 else "DOWN" if pct_change < 0 else "FLAT"
        
        header = (
            f"Realized {symbol} move on {trading_date}: "
            f"closed at ${close_today:.2f} vs ${close_prev:.2f} "
            f"({pct_change:+.2f}%), overall {direction} day.\n\n"
        )
        
        return header
        
    except Exception as e:
        logger.error("Error building realized move header for %s: %s", symbol, e)
        return ""

