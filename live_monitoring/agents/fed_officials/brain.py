"""
🧠 Fed Officials Brain — The Actual Brain
==========================================
No bloat. No dead imports. No hardcoded if-statements.

Uses the live pipes we already compromised:
- Diffbot for clean Fed speech transcripts
- Direct SQLite queries on politician_trades + insider_trades (already populated)
- Feeds divergence score + NarrativeEngine directly via get_brain_report()
"""

import os
import hashlib
import logging
import sqlite3
import feedparser
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class FedOfficialsBrain:
    """
    The actual brain. No bloat.
    
    One call to get_brain_report() → everything the NarrativeEngine needs:
      - Fed speech tones (Diffbot-extracted, LLM-analyzed)
      - Politician cluster buys (live SQLite)
      - Insider net buying (live SQLite)
      - Divergence boost + reasons ready for signal_generator
    """

    def __init__(self, db=None):
        # Reuse existing DB or create fresh connection
        if db is None:
            from live_monitoring.agents.fed_officials.database import FedOfficialsDatabase
            self.db = FedOfficialsDatabase()
            self._conn = sqlite3.connect(self.db.db_path)
        elif hasattr(db, 'db_path'):
            self.db = db
            self._conn = sqlite3.connect(db.db_path)
        else:
            self._conn = db  # raw connection
            self.db = None

        # ⚡ Zeta Cache Control
        self._cache_report = None
        self._last_scan = None
        self._cache_ttl = timedelta(minutes=15)

        self.diffbot_token = os.getenv("DIFFBOT_TOKEN")
        self._seen_urls = set()

        # Finnhub client for insider MSPR + news enrichment
        try:
            from live_monitoring.enrichment.apis.finnhub_client import FinnhubClient
            self.finnhub = FinnhubClient()
        except Exception:
            self.finnhub = None

        # Load Diffbot extractor
        try:
            from live_monitoring.enrichment.apis.diffbot_extractor import DiffbotExtractor
            self.extractor = DiffbotExtractor()
        except ImportError:
            self.extractor = None
            logger.warning("DiffbotExtractor not available")

        # Load Tavily research client
        self.tavily = None
        try:
            tavily_key = os.getenv("TAVILY_API_KEY")
            if tavily_key:
                from tavily import TavilyClient
                self.tavily = TavilyClient(api_key=tavily_key)
                logger.info("✅ Tavily research client initialized")
        except ImportError:
            logger.warning("tavily-python not installed — run: pip install tavily-python")

        # Load sentiment analyzer (LLM-based)
        try:
            from live_monitoring.agents.fed_officials.sentiment_analyzer import SentimentAnalyzer
            if self.db:
                self.sentiment = SentimentAnalyzer(self.db)
            else:
                self.sentiment = None
        except ImportError:
            self.sentiment = None

    # ── Fed Speeches ─────────────────────────────────────────────────────────

    def scan_fed_speeches(self, hours: int = 24) -> List[Dict]:
        """Diffbot + RSS → clean transcripts + tone.
        Uses DB comment_hash for persistent dedup — survives restarts."""
        feed = feedparser.parse("https://www.federalreserve.gov/feeds/speeches.xml")

        # Persistent dedup: check DB for existing hashes, not just RAM
        existing_hashes = set()
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT url FROM comments WHERE url IS NOT NULL")
            existing_hashes = {row[0] for row in cursor.fetchall()}
        except Exception:
            pass  # Table might not exist yet — normal on first run

        new_items = [
            e for e in feed.entries[:5]
            if e.link not in self._seen_urls and e.link not in existing_hashes
        ]

        results = []
        for item in new_items:
            self._seen_urls.add(item.link)
            speech = self._diffbot_extract(item.link)
            if speech and speech.get("full_text"):
                # Parse speaker from title: "Bowman, Liquidity Resiliency..." → "Bowman"
                speaker = speech.get("speaker") or ""
                if not speaker and "," in item.title:
                    speaker = item.title.split(",")[0].strip()
                if not speaker:
                    speaker = "Fed Official"

                tone, confidence, reasoning = self._analyze_tone(
                    speech["full_text"], speaker
                )
                result = {
                    "official": speaker,
                    "title": item.title,
                    "tone": tone,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "text_preview": speech["full_text"][:300],
                    "url": item.link,
                    "date": speech.get("date", datetime.now().isoformat()),
                }
                self._save_fed_comment(result)
                results.append(result)
            else:
                logger.debug(f"Diffbot returned no text for {item.link}")

        return results

    # ── Self-Healing Data Pipeline ────────────────────────────────────────────

    def _ensure_hidden_hands_data(self):
        """If DB has no recent trades, trigger the scrapers to populate.
        Self-healing: brain doesn't depend on external cron to have data."""
        try:
            cursor = self._conn.cursor()

            # Check if politician_trades has any recent rows
            cursor.execute("""
                SELECT COUNT(*) FROM politician_trades
                WHERE created_at >= datetime('now', '-1 days')
            """)
            pol_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM insider_trades
                WHERE created_at >= datetime('now', '-1 days')
            """)
            ins_count = cursor.fetchone()[0]

            if pol_count > 0 and ins_count > 0:
                logger.debug(f"DB has fresh data: {pol_count} pol trades, {ins_count} insider trades")
                return

            # DB is stale/empty — trigger scrapers
            logger.info("DB has no recent hidden hands data. Triggering scrapers...")
            try:
                from live_monitoring.agents.fed_officials.engine import FedOfficialsEngine
                engine = FedOfficialsEngine()
                results = engine.fetch_hidden_layers()
                logger.info(f"Scrapers populated: {results}")
            except Exception as e:
                logger.warning(f"Scraper self-heal failed (non-fatal): {e}")

        except Exception as e:
            # Tables might not exist yet — DB init happens on FedOfficialsDatabase()
            logger.debug(f"Hidden hands check skipped: {e}")
            try:
                # Force DB init if tables don't exist
                from live_monitoring.agents.fed_officials.database import FedOfficialsDatabase
                FedOfficialsDatabase()
                logger.info("DB tables initialized on first run")
            except Exception as e:
                logger.warning(f"DB table init failed: {e}")

    # ── DRIP / Routine Trade Detection ────────────────────────────────────────

    def _detect_routine_trades(self) -> set:
        """Detect routine/DRIP trades: same (politician, ticker, direction) appearing 3+ times.
        Returns a set of (politician_name, ticker, transaction_type) tuples that are routine."""
        routine_keys = set()
        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT politician_name, ticker, transaction_type, COUNT(*) as cnt
                FROM politician_trades
                GROUP BY politician_name, ticker, transaction_type
                HAVING cnt >= 3
            """)
            for row in cursor.fetchall():
                routine_keys.add((row[0], row[1], row[2]))
                logger.info(f"DRIP filter: {row[0]} {row[1]} {row[2]} flagged ROUTINE ({row[3]} occurrences)")
        except sqlite3.OperationalError:
            pass
        return routine_keys

    # ── Hidden Hands (Direct SQLite — reads what scrapers wrote) ──────────────

    def scan_hidden_hands(self, days: int = 7) -> Dict:
        """Exploit the live pipes we already opened. Direct SQL on populated tables."""
        cursor = self._conn.cursor()

        # Detect routine/DRIP trades before processing
        routine_keys = self._detect_routine_trades()

        # Politician trades — table may not exist on fresh Render deploy
        pol_rows = []
        try:
            cursor.execute("""
                SELECT politician_name, ticker, transaction_type, trade_size, trade_date, owner
                FROM politician_trades
                WHERE created_at >= datetime('now', ? || ' days')
                ORDER BY created_at DESC LIMIT 20
            """, (f"-{days}",))
            pol_rows = cursor.fetchall()
        except sqlite3.OperationalError as e:
            logger.warning(f"politician_trades query failed (table may not exist): {e}")

        # Insider trades — same resilience
        ins_rows = []
        try:
            cursor.execute("""
                SELECT executive_name, company, ticker, transaction_type, trade_value_usd, trade_date
                FROM insider_trades
                WHERE created_at >= datetime('now', ? || ' days')
                ORDER BY created_at DESC LIMIT 20
            """, (f"-{days}",))
            ins_rows = cursor.fetchall()
        except sqlite3.OperationalError as e:
            logger.warning(f"insider_trades query failed (table may not exist): {e}")

        # Compute net insider buying
        insider_buys = sum(
            row[4] for row in ins_rows
            if row[3] and ('purchase' in row[3].lower() or 'p -' in row[3].lower())
            and row[4] is not None
        )
        insider_sells = sum(
            row[4] for row in ins_rows
            if row[3] and ('sale' in row[3].lower() or 's -' in row[3].lower())
            and row[4] is not None
        )

        # Extract unique hot tickers
        pol_tickers = [row[1] for row in pol_rows if row[1]]
        ins_tickers = [row[2] for row in ins_rows if row[2]]
        hot_tickers = list(set(pol_tickers + ins_tickers))

        # Politician buy vs sell — EXCLUDE routine/DRIP trades from signal counts
        pol_buys_discretionary = sum(
            1 for row in pol_rows
            if row[2] and 'buy' in row[2].lower()
            and (row[0], row[1], row[2]) not in routine_keys
        )
        pol_sells_discretionary = sum(
            1 for row in pol_rows
            if row[2] and 'sell' in row[2].lower()
            and (row[0], row[1], row[2]) not in routine_keys
        )
        pol_buys_total = sum(1 for row in pol_rows if row[2] and 'buy' in row[2].lower())
        pol_sells_total = sum(1 for row in pol_rows if row[2] and 'sell' in row[2].lower())

        # Build politician details with is_routine + owner flags
        politician_details = []
        for r in pol_rows:
            owner = r[5] if len(r) > 5 else 'Self'
            is_routine = (r[0], r[1], r[2]) in routine_keys
            politician_details.append({
                "name": r[0], "ticker": r[1], "type": r[2],
                "size": r[3], "date": r[4], "owner": owner or 'Self',
                "is_routine": is_routine,
            })

        return {
            "politician_cluster": len(pol_rows),
            "politician_buys": pol_buys_discretionary,
            "politician_sells": pol_sells_discretionary,
            "politician_buys_total": pol_buys_total,
            "politician_sells_total": pol_sells_total,
            "insider_net_usd": insider_buys - insider_sells,
            "insider_buys_usd": insider_buys,
            "insider_sells_usd": insider_sells,
            "insider_count": len(ins_rows),
            "hot_tickers": hot_tickers,
            "politician_details": politician_details,
            "insider_details": [
                {"name": r[0], "company": r[1], "ticker": r[2], "type": r[3], "value": r[4], "date": r[5]}
                for r in ins_rows[:5]
            ],
        }

    # ── The One Call ─────────────────────────────────────────────────────────

    def get_brain_report(self, force_refresh: bool = False) -> Dict:
        """
        One call → everything the NarrativeEngine and SignalGenerator need.
        15-min TTL Cache implemented for Zeta efficiency. {in Zeta, asked by Alpha}
        """
        now = datetime.now()
        
        if not force_refresh and self._cache_report and self._last_scan:
            if now - self._last_scan < self._cache_ttl:
                logger.debug("🚀 Zeta Cache Hit. Serving fresh intelligence.")
                return self._cache_report

        logger.info("🔍 Brain Refreshing. Scanning speeches and hidden hands...")

        # Self-heal: populate DB if hidden hands tables are empty/stale
        self._ensure_hidden_hands_data()

        fed = self.scan_fed_speeches(hours=24)
        hands = self.scan_hidden_hands(days=7)

        divergence_boost = 0
        reasons = []

        # Politician cluster conviction (DRIP-filtered — only discretionary trades count)
        routine_count = sum(1 for d in hands.get('politician_details', []) if d.get('is_routine'))
        if routine_count > 0:
            reasons.append(
                f"⚠️ {routine_count} ROUTINE trade(s) detected (DRIP/quarterly) — excluded from divergence"
            )
        if hands["politician_buys"] >= 3:
            divergence_boost += 2
            reasons.append(
                f"Politician cluster buys detected ({hands['politician_buys']} discretionary buys in "
                f"{', '.join(hands['hot_tickers'][:3])})"
            )

        # Insider net buying conviction
        if hands["insider_net_usd"] > 5_000_000:
            divergence_boost += 3
            reasons.append(
                f"Insider net buying ${hands['insider_net_usd']/1e6:.1f}M "
                f"({hands['insider_count']} trades)"
            )
        elif hands["insider_net_usd"] > 1_000_000:
            divergence_boost += 1
            reasons.append(
                f"Insider net buying ${hands['insider_net_usd']/1e6:.1f}M"
            )

        # Insider dumping = reduce conviction
        if hands["insider_sells_usd"] > hands["insider_buys_usd"] and hands["insider_count"] >= 3:
            divergence_boost -= 2
            reasons.append(
                f"⚠️ Insider net SELLING ${abs(hands['insider_net_usd'])/1e6:.1f}M — conviction down"
            )

        # Finnhub MSPR cross-reference — convergence/divergence with insiders
        # SKIP routine/DRIP trades — they have zero signal value
        finnhub_signals = []
        if self.finnhub and hands["hot_tickers"]:
            for detail in hands.get("politician_details", [])[:5]:
                is_routine = detail.get("is_routine", False)
                try:
                    ticker = detail["ticker"]
                    xref = self.finnhub.cross_reference_politician_trade(
                        ticker=ticker,
                        politician_action=detail.get("type", "buy"),
                    )
                    if xref and xref.get("convergence") != "unknown":
                        # Routine trades get 0 divergence boost — mechanical, no signal
                        if not is_routine:
                            # Cap per-ticker boost at 2 to prevent score inflation
                            _ticker_boost = min(xref.get("divergence_boost", 0), 2)
                            divergence_boost += _ticker_boost
                        else:
                            xref["routine_flag"] = True
                            xref["reasoning"] = xref.get("reasoning", []) + [
                                f"⚠️ ROUTINE: {detail['name']} has traded {ticker} 3+ times — DRIP/mechanical"
                            ]
                        for r in xref.get("reasoning", []):
                            reasons.append(f"Finnhub: {r}")
                        finnhub_signals.append(xref)

                    # Save per-person SEC filings to DB (not just MSPR)
                    if self.db:
                        try:
                            insider_txs = self.finnhub.get_insider_transactions(ticker, limit=5)
                            for tx in insider_txs:
                                self.db.save_insider_trade({
                                    "executive_name": tx.get("name", "Unknown"),
                                    "company": ticker,
                                    "ticker": ticker,
                                    "transaction_type": tx.get("type", "unknown"),
                                    "trade_value_usd": tx.get("value_usd", 0),
                                    "trade_date": tx.get("transaction_date", ""),
                                    "filing_date": tx.get("filing_date", ""),
                                    "url": f"https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}",
                                })
                        except Exception as e:
                            logger.debug(f"Finnhub insider tx save failed for {ticker}: {e}")
                except Exception as e:
                    logger.debug(f"Finnhub cross-ref failed for {detail.get('ticker')}: {e}")

        # Fed tone alignment
        hawkish = sum(1 for s in fed if s["tone"] == "HAWKISH")
        dovish = sum(1 for s in fed if s["tone"] == "DOVISH")
        if hawkish > dovish:
            reasons.append(f"Fed tone: HAWKISH ({hawkish} hawks vs {dovish} doves)")
        elif dovish > hawkish:
            reasons.append(f"Fed tone: DOVISH ({dovish} doves vs {hawkish} hawks)")

        # Finnhub news first (free), then Tavily only if needed
        finnhub_news = {}
        tavily_context = None
        if self.finnhub and hands["hot_tickers"]:
            for ticker in hands["hot_tickers"][:3]:
                try:
                    news = self.finnhub.get_company_news(ticker, days=7, limit=5)
                    if news:
                        finnhub_news[ticker] = news
                except Exception:
                    pass

        # Tavily only if Finnhub missed or for deeper "why" questions
        if not finnhub_news and hands["hot_tickers"] and (
            hands["politician_buys"] >= 2 or hands["insider_count"] >= 3
        ):
            tavily_context = self.enrich_with_tavily(
                hot_tickers=hands["hot_tickers"][:5],
                fed_tone=fed[0]["tone"] if fed else None,
            )
            if tavily_context and tavily_context.get("relevance_score", 0) > 0.5:
                divergence_boost += 1
                reasons.append(
                    f"Tavily research: {tavily_context['summary'][:150]}..."
                )

        report = {
            "fed_tone_summary": fed,
            "fed_hawkish_count": hawkish,
            "fed_dovish_count": dovish,
            "fed_overall_tone": "HAWKISH" if hawkish > dovish else ("DOVISH" if dovish > hawkish else "NEUTRAL"),
            "hidden_hands": hands,
            "finnhub_signals": finnhub_signals,
            "finnhub_news": finnhub_news,
            "spouse_alerts": self._get_spouse_alerts(),
            "fed_calendar_events": self._get_calendar_events(),
            "tavily_context": tavily_context,
            "divergence_boost": max(min(divergence_boost, 6), -4),  # cap: max +6, min -4
            "reasons": reasons,
            "timestamp": now.isoformat(),
        }

        # ⚡ Store in Zeta cache
        self._cache_report = report
        self._last_scan = now
        
        return report

    # ── Internal Helpers ─────────────────────────────────────────────────────

    def _get_spouse_alerts(self) -> List[Dict]:
        """Surface spouse trade alerts from DB. Queries the `owner` column."""
        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT politician_name, ticker, transaction_type, trade_size, trade_date, owner
                FROM politician_trades
                WHERE LOWER(owner) = 'spouse'
                   OR LOWER(owner) = 'joint'
                ORDER BY created_at DESC LIMIT 10
            """)
            rows = cursor.fetchall()
            return [
                {
                    "politician": r[0], "ticker": r[1], "type": r[2],
                    "size": r[3], "date": r[4], "owner": r[5],
                    "alert": "SPOUSE TRADE"
                }
                for r in rows
            ]
        except Exception:
            return []

    def _get_calendar_events(self) -> List[Dict]:
        """Surface upcoming Fed calendar events. These were fetched but discarded."""
        try:
            from live_monitoring.agents.fed_officials.fed_rss_calendar import FedRSSCalendarPoller
            poller = FedRSSCalendarPoller()
            events = poller.poll_calendar()
            return [
                {
                    "title": e.get("title", ""),
                    "date": e.get("date", ""),
                    "type": e.get("type", ""),
                    "speaker": e.get("speaker", ""),
                }
                for e in (events or [])[:10]
            ]
        except Exception:
            return []

    def _diffbot_extract(self, url: str) -> Optional[Dict]:
        """Use Diffbot Article API for clean speech transcript."""
        if not self.extractor:
            return None
        return self.extractor.extract_article(url)

    def _analyze_tone(self, text: str, speaker: str) -> tuple:
        """LLM tone analysis. Falls back to keyword if no LLM."""
        if self.sentiment:
            return self.sentiment.analyze(text[:2000], speaker)
        # Emergency fallback
        text_lower = text.lower()
        if any(w in text_lower for w in ["inflation", "restrictive", "higher for longer", "not ready to cut"]):
            return "HAWKISH", 0.5, "Keyword fallback"
        if any(w in text_lower for w in ["rate cut", "easing", "progress on inflation", "labor cooling"]):
            return "DOVISH", 0.5, "Keyword fallback"
        return "NEUTRAL", 0.3, "No clear signal"

    def _save_fed_comment(self, result: Dict):
        """Save to comments table if DB is available."""
        if not self.db:
            return
        try:
            from live_monitoring.agents.fed_officials.models import FedComment
            comment = FedComment(
                timestamp=datetime.now(),
                official_name=result["official"],
                headline=result["title"],
                content=result.get("text_preview", ""),
                source="Federal Reserve RSS (Diffbot)",
                url=result.get("url", ""),
                sentiment=result["tone"],
                sentiment_confidence=result["confidence"],
                sentiment_reasoning=result["reasoning"],
                predicted_market_impact="UNKNOWN",
                comment_hash=hashlib.md5(
                    f"{result['official']}:{result.get('text_preview', '')[:100]}".encode()
                ).hexdigest(),
            )
            self.db.save_comment(comment)
        except Exception as e:
            logger.debug(f"Failed to save Fed comment: {e}")

    def is_new(self, url: str) -> bool:
        """Check if we've already processed this URL."""
        return url not in self._seen_urls

    # ── Tavily Research ──────────────────────────────────────────────────────

    def enrich_with_tavily(
        self,
        hot_tickers: List[str],
        fed_tone: Optional[str] = None,
        politician_name: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Real-time web research on hot tickers from hidden hands.
        Returns clean LLM-ready context: summary, sources, relevance score.
        """
        if not self.tavily:
            return None

        # Build smart query based on what we know
        ticker_str = ', '.join(hot_tickers[:5])
        if politician_name:
            query = f"{politician_name} stock trades {ticker_str} why buying reason market impact 2026"
        elif fed_tone:
            query = (f"insider and politician buying {ticker_str} while Fed tone {fed_tone} "
                     f"market impact institutional positioning 2026")
        else:
            query = f"why insiders politicians buying {ticker_str} March 2026 market catalyst earnings"

        try:
            response = self.tavily.search(
                query=query,
                max_results=5,
                search_depth="advanced",
                include_raw_content=False,  # save credits, summaries are enough
            )
            results = response.get("results", [])
            if not results:
                return None

            # Build enrichment dict
            top = results[0]
            return {
                "query": query,
                "summary": top.get("content", "")[:500],
                "sources": [r.get("url", "") for r in results[:5]],
                "relevance_score": top.get("score", 0),
                "all_summaries": [
                    {"title": r.get("title", ""), "content": r.get("content", "")[:200], "score": r.get("score", 0)}
                    for r in results[:3]
                ],
            }

        except Exception as e:
            logger.warning(f"Tavily research failed: {e}")
            return None
