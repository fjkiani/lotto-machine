# Enhanced Manager Review System

## Overview

The Enhanced Manager Review System is a configurable, rules-based framework for detecting and resolving contradictions in financial analysis. It serves as a quality control layer that validates analysis for logical consistency, identifies potential issues, and automatically applies fixes when possible.

Key features include:

- **Configuration-based rules**: Rules, thresholds, and severity levels defined in YAML
- **Automated contradiction detection**: Identifies logical inconsistencies in analysis
- **Dynamic rule management**: Add, remove, or modify rules at runtime
- **Confidence scoring**: Quantifies analysis reliability based on contradiction severity
- **Detailed review notes**: Explains identified issues and resolution steps
- **Automatic fixes**: Resolves common contradictions without manual intervention

## Configuration

The system uses a YAML configuration file (`config/manager_review_config.yaml`) with the following structure:

```yaml
# Validation thresholds
thresholds:
  price_overlap: 0.01  # 1% overlap between support and resistance
  volatility_high: 60  # IV rank threshold for high volatility
  volume_significance: 5000  # Volume threshold for significance

# Confidence score penalties
confidence_penalties:
  high_severity: 0.3
  medium_severity: 0.2
  low_severity: 0.1

# Analysis rules
rules:
  sentiment_strategy:
    conditions:
      - type: "bullish_put"
        check: "market_state.get('overall_sentiment') == 'bullish' and any('put' in str(s.get('strategy', '')).lower() for s in trading_opportunities.get('strategies', []))"
        severity: "high"
        description: "Bullish market sentiment conflicts with put-focused strategy"
        recommendation: "Consider aligning strategy with bullish outlook using calls or call spreads"
    severity: "high"
    
  price_levels:
    conditions:
      - type: "close_levels"
        check: "abs(price_levels.get('resistance', 0) - price_levels.get('support', 0)) / price_levels.get('current_price', 100) < thresholds.get('price_overlap', 0.01)"
        severity: "medium"
        description: "Support and resistance levels are too close (less than {thresholds[price_overlap]:.0%} apart)"
        recommendation: "Reconsider support/resistance identification or look for additional technical levels"
    severity: "medium"
    
  volatility_risk:
    conditions:
      - type: "high_vol_large_size"
        check: "volatility_structure.get('skew', '') == 'high' and any(s.get('size', '') == 'large' for s in trading_opportunities.get('strategies', []))"
        severity: "high"
        description: "High volatility environment with large position size recommendations"
        recommendation: "Consider reducing position size or using spreads to manage risk"
    severity: "high"
```

## Usage

### Basic Usage

```python
from src.llm.enhanced_manager_review import EnhancedManagerReview

# Initialize the enhanced manager
enhanced_manager = EnhancedManagerReview()

# Review analysis
result = enhanced_manager.review_analysis(analysis)

# Check if contradictions were found
if result != analysis:
    # Get confidence score
    confidence_score = result.get("confidence_score", 0.0)
    
    # Get contradiction details
    contradictions = result.get("contradictions_found", [])
    
    # Get the resolved analysis
    resolved_analysis = result.get("resolved_analysis", {})
    
    # Get review notes
    review_notes = result.get("review_notes", "")
    
    # Get list of changes made
    changes = result.get("changes_made", [])
```

### Adding Custom Rules at Runtime

```python
from src.llm.enhanced_manager_review import EnhancedManagerReview

# Initialize the enhanced manager
enhanced_manager = EnhancedManagerReview()

# Create a custom rule
earnings_rule = {
    "conditions": [
        "any(risk.get('type') == 'earnings' for risk in analysis.get('risk_factors', []) if isinstance(risk, dict)) and "
        "any(opp.get('position_size') == 'large' for opp in analysis.get('trading_opportunities', []) if isinstance(opp, dict))"
    ],
    "severity": "high",
    "description": "Found large position size recommendation with upcoming earnings event, which increases risk",
    "recommendation": "Consider reducing position size before earnings or using defined risk strategies like spreads",
}

# Add the custom rule
enhanced_manager.add_custom_rule("earnings_position_mismatch", earnings_rule)

# Later, remove the rule if needed
enhanced_manager.remove_custom_rule("earnings_position_mismatch")

# List all available rules
rules = enhanced_manager.list_rules()
print(f"Built-in rules: {len(rules['built_in'])}")
print(f"Custom rules: {len(rules['custom'])}")
```

## Integration with Options Analysis

The system is integrated with the options analysis pipeline through the following functions:

```python
# Standard analysis with basic review
result = analyze_options_chain_with_review(ticker, market_data, options_chain)

# Enhanced analysis with advanced review and automatic fixes
result = analyze_options_chain_with_enhanced_review(ticker, market_data, options_chain, risk_tolerance="medium")
```

## Rule Conditions

Rule conditions are defined as Python expressions evaluated at runtime. Available context variables include:

- `analysis`: The complete analysis dictionary
- `market_state`: Market sentiment information
- `price_levels`: Support and resistance levels
- `volatility_structure`: Volatility metrics and skew information
- `institutional_flows`: Institutional activity data
- `trading_opportunities`: Recommended strategies
- `risk_factors`: Identified risk factors
- `technical_signals`: Technical analysis indicators
- `thresholds`: Configuration thresholds

## Contradiction Resolution

When contradictions are detected, the system can automatically resolve them using predefined fix methods:

1. **Sentiment-Strategy Mismatch**: Aligns trading strategies with market sentiment
2. **Price Levels Contradiction**: Adjusts support/resistance levels when too close
3. **Volatility-Risk Mismatch**: Reduces position sizes in high volatility conditions
4. **Technical-Institutional Mismatch**: Adds warnings when technical and institutional signals conflict

## Confidence Scoring

The system calculates a confidence score for each analysis based on:

1. Base confidence (starts at 1.0)
2. Deductions for each contradiction based on severity
3. Penalties defined in configuration:
   - High severity: 0.3 deduction
   - Medium severity: 0.2 deduction
   - Low severity: 0.1 deduction

## Testing

Run tests using the provided test script:

```bash
# Run all tests
python tools/test_enhanced_manager.py

# Run only standard tests
python tools/test_enhanced_manager.py --test-type standard

# Run only custom rule tests
python tools/test_enhanced_manager.py --test-type custom
```

## Implementation Details

### Key Classes

- **EnhancedManagerReview**: Main class handling contradiction detection and resolution
- **Rule**: Class representing a single validation rule with condition and severity

### Important Methods

- `review_analysis()`: Main entry point for analysis review
- `_apply_recommendations()`: Applies automatic fixes to resolve contradictions
- `_calculate_confidence()`: Computes confidence score based on contradictions
- `_generate_review_notes()`: Creates human-readable summary of issues
- `add_custom_rule()`: Adds a new rule at runtime
- `remove_custom_rule()`: Removes a previously added custom rule
- `list_rules()`: Lists all available rules

## Best Practices

1. **Rule Design**:
   - Make rules specific and focused on single issues
   - Use clear descriptions that explain the contradiction
   - Provide actionable recommendations
   - Implement fix methods for common issues

2. **Configuration Management**:
   - Version control your configuration files
   - Use environment-specific configurations
   - Validate thresholds regularly against market conditions
   - Document rule changes

3. **Integration**:
   - Always capture both original and resolved analysis
   - Log contradiction details and resolutions
   - Track confidence scores over time
   - Monitor false positives/negatives

4. **Custom Rules**:
   - Test custom rules thoroughly before deployment
   - Use the rule removal capability for temporary rules
   - Migrate successful custom rules to configuration 