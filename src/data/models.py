from pydantic import BaseModel
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Union, Literal, Any
from decimal import Decimal


class Price(BaseModel):
    open: float
    close: float
    high: float
    low: float
    volume: int
    time: str


class PriceResponse(BaseModel):
    ticker: str
    prices: list[Price]


class FinancialMetrics(BaseModel):
    ticker: str
    calendar_date: str
    report_period: str
    period: str
    currency: str
    market_cap: float | None
    enterprise_value: float | None
    price_to_earnings_ratio: float | None
    price_to_book_ratio: float | None
    price_to_sales_ratio: float | None
    enterprise_value_to_ebitda_ratio: float | None
    enterprise_value_to_revenue_ratio: float | None
    free_cash_flow_yield: float | None
    peg_ratio: float | None
    gross_margin: float | None
    operating_margin: float | None
    net_margin: float | None
    return_on_equity: float | None
    return_on_assets: float | None
    return_on_invested_capital: float | None
    asset_turnover: float | None
    inventory_turnover: float | None
    receivables_turnover: float | None
    days_sales_outstanding: float | None
    operating_cycle: float | None
    working_capital_turnover: float | None
    current_ratio: float | None
    quick_ratio: float | None
    cash_ratio: float | None
    operating_cash_flow_ratio: float | None
    debt_to_equity: float | None
    debt_to_assets: float | None
    interest_coverage: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    book_value_growth: float | None
    earnings_per_share_growth: float | None
    free_cash_flow_growth: float | None
    operating_income_growth: float | None
    ebitda_growth: float | None
    payout_ratio: float | None
    earnings_per_share: float | None
    book_value_per_share: float | None
    free_cash_flow_per_share: float | None


class FinancialMetricsResponse(BaseModel):
    financial_metrics: list[FinancialMetrics]


class LineItem(BaseModel):
    ticker: str
    report_period: str
    period: str
    currency: str

    # Allow additional fields dynamically
    model_config = {"extra": "allow"}


class LineItemResponse(BaseModel):
    search_results: list[LineItem]


class InsiderTrade(BaseModel):
    ticker: str
    issuer: str | None
    name: str | None
    title: str | None
    is_board_director: bool | None
    transaction_date: str | None
    transaction_shares: float | None
    transaction_price_per_share: float | None
    transaction_value: float | None
    shares_owned_before_transaction: float | None
    shares_owned_after_transaction: float | None
    security_title: str | None
    filing_date: str


class InsiderTradeResponse(BaseModel):
    insider_trades: list[InsiderTrade]


class CompanyNews(BaseModel):
    ticker: str
    title: str
    author: str
    source: str
    date: str
    url: str
    sentiment: str | None = None


class CompanyNewsResponse(BaseModel):
    news: list[CompanyNews]


class Position(BaseModel):
    cash: float = 0.0
    shares: int = 0
    ticker: str


class Portfolio(BaseModel):
    positions: dict[str, Position]  # ticker -> Position mapping
    total_cash: float = 0.0


class AnalystSignal(BaseModel):
    signal: str | None = None
    confidence: float | None = None
    reasoning: dict | str | None = None
    max_position_size: float | None = None  # For risk management signals


class TickerAnalysis(BaseModel):
    ticker: str
    analyst_signals: dict[str, AnalystSignal]  # agent_name -> signal mapping


class AgentStateData(BaseModel):
    tickers: list[str]
    portfolio: Portfolio
    start_date: str
    end_date: str
    ticker_analyses: dict[str, TickerAnalysis]  # ticker -> analysis mapping


class AgentStateMetadata(BaseModel):
    show_reasoning: bool = False
    model_config = {"extra": "allow"}


@dataclass
class OptionContract:
    contract_symbol: str
    option_type: Literal["CALL", "PUT"]
    strike: Decimal
    currency: Optional[str] = None
    last_price: Optional[Decimal] = None
    change_price: Optional[Decimal] = None
    percent_change: Optional[Decimal] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    contract_size: Optional[str] = None
    expiration: Optional[datetime] = None
    last_trade_date: Optional[datetime] = None
    implied_volatility: Optional[Decimal] = None
    in_the_money: Optional[bool] = None
    
    # Calculated Greeks (not in original schema but useful for analysis)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None


@dataclass
class OptionStraddle:
    strike: Decimal
    call_contract: Optional[OptionContract] = None
    put_contract: Optional[OptionContract] = None


@dataclass
class OptionChainOptions:
    expiration_date: datetime
    has_mini_options: bool
    straddles: List[OptionStraddle] = None


@dataclass
class OptionChainQuote:
    quote_type: Optional[str] = None
    market_state: Optional[str] = None
    currency: Optional[str] = None
    regular_market_price: Optional[Decimal] = None
    regular_market_change: Optional[Decimal] = None
    regular_market_change_percent: Optional[Decimal] = None
    regular_market_open: Optional[Decimal] = None
    regular_market_day_high: Optional[Decimal] = None
    regular_market_day_low: Optional[Decimal] = None
    regular_market_volume: Optional[int] = None
    market_cap: Optional[int] = None
    trailing_pe: Optional[Decimal] = None
    trailing_annual_dividend_rate: Optional[Decimal] = None
    dividend_rate: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    eps_trailing_twelve_months: Optional[Decimal] = None
    eps_forward: Optional[Decimal] = None
    eps_current_year: Optional[Decimal] = None


@dataclass
class OptionChain:
    underlying_symbol: str
    has_mini_options: bool
    quote: Optional[OptionChainQuote] = None
    expiration_dates: List[datetime] = None
    strikes: List[Decimal] = None
    options: List[OptionChainOptions] = None
    raw_json: Optional[Dict] = None


@dataclass
class MarketQuote:
    """Detailed market quote data from Yahoo Finance marketGetQuotesV2 endpoint"""
    symbol: str
    quote_type: str
    market_state: str
    regular_market_price: float
    regular_market_previous_close: float
    regular_market_open: float
    regular_market_day_high: float
    regular_market_day_low: float
    regular_market_volume: int
    average_volume: int
    average_volume_10_days: int
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    market_cap: float
    fifty_two_week_high: float
    fifty_two_week_low: float
    fifty_day_average: float
    two_hundred_day_average: float
    trailing_annual_dividend_rate: float
    trailing_annual_dividend_yield: float
    trailing_pe: float
    exchange: str
    exchange_name: str
    currency: str
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def get_price_to_book(self) -> Optional[float]:
        """Calculate price to book ratio if available"""
        if "priceToBook" in self.raw_data:
            return self.raw_data["priceToBook"]
        return None
    
    def get_dividend_yield(self) -> float:
        """Get the dividend yield as a percentage"""
        return self.trailing_annual_dividend_yield * 100
    
    def get_price_to_earnings(self) -> float:
        """Get the price to earnings ratio"""
        return self.trailing_pe
    
    def is_market_open(self) -> bool:
        """Check if the market is currently open"""
        return self.market_state in ["REGULAR", "PRE", "POST"]
    
    def get_day_change_percent(self) -> float:
        """Calculate the day's price change as a percentage"""
        if self.regular_market_previous_close > 0:
            return ((self.regular_market_price - self.regular_market_previous_close) / 
                    self.regular_market_previous_close) * 100
        return 0
    
    def get_day_range_percent(self) -> float:
        """Calculate the day's price range as a percentage of the current price"""
        if self.regular_market_price > 0:
            return ((self.regular_market_day_high - self.regular_market_day_low) / 
                    self.regular_market_price) * 100
        return 0
