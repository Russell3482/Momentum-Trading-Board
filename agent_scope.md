# Momentum Trading Agent

## Objective

Build a daily momentum trading research assistant focused on identifying high-probability 1-3 month momentum setups.

The agent does not provide financial advice.

The agent's purpose is to:

- Identify strong momentum stocks
- Detect breakout opportunities
- Monitor trend quality
- Alert on momentum deterioration
- Generate concise daily reports

The agent assumes the watchlist has already passed the user's qualitative quality filter. The model's job is not to decide whether a company is fundamentally excellent; it is to decide which watchlist names are closest to an actionable technical entry.

## Trading Philosophy

This system is primarily a timing scanner based on:

### Mark Minervini

Responsible for:

- Trend Template
- VCP / contraction quality
- Breakout readiness
- Risk management

Purpose:

- Find the right entry.

### Dan Zanger

Responsible for:

- Explosive volume
- Momentum acceleration
- High tight flag behavior
- Gap and acceleration phases

Purpose:

- Identify acceleration phases.

### William O'Neil

O'Neil-style company quality and industry leadership are treated as upstream watchlist construction inputs, not as scoring components inside this model. Earnings growth, institutional sponsorship, and CAN SLIM fundamentals are intentionally excluded from the daily score unless the user later provides a fundamental data source.

Purpose:

- Avoid mixing long-term company quality with short-term entry timing.

## Market Focus

Primary sectors:

- AI Infrastructure
- Semiconductors
- Memory
- Networking
- PCB
- Power & Cooling
- Datacenter

Primary watchlist:

- INTC
- STM
- AMD
- MU
- NVDA
- BE
- TTMI
- SNDK
- MXL
- LITE
- AVGO
- CIEN

Benchmark indexes:

- QQQ
- SOXX
- SMH

No stock should be analyzed in isolation.

## Daily Workflow

Every market close:

1. Update market data
2. Evaluate watchlist
3. Calculate Timing Score
4. Detect setup and breakout readiness
5. Generate report
6. Generate alerts

## Trend Template

A stock is considered Trend Qualified when:

- Price > 50DMA
- Price > 150DMA
- Price > 200DMA
- 50DMA > 150DMA
- 150DMA > 200DMA
- Price within 25% of 52-week high

Classification:

- Pass = Trend Qualified
- Fail = Not Qualified

## Relative Strength Analysis

Measure:

- 1 Week Return
- 1 Month Return
- 3 Month Return

Compare against:

- SOXX
- QQQ

Interpretation:

- Outperforming = Positive
- Underperforming = Negative

## VCP Detection

Detect contraction history, not decorative labels:

- Recent pullback depth sequence
- Whether pullbacks are getting shallower
- Whether pullback volume is drying up
- Whether price remains near pivot/resistance

Example:

- 20%
- 10%
- 5%

Requirements:

- Volatility decreases
- Volume decreases
- Price remains near highs

Classification:

- Clean contraction
- Developing contraction
- Messy contraction
- No contraction

## Breakout Detection

### Pivot

Pivot is defined as the most recent significant high.

### Breakout Confirmation

Must satisfy all:

- Daily close > pivot
- Volume > 1.5x 20-day average volume

Classification:

- Breakout Watch
- Breakout Attempt
- Confirmed Breakout
- Failed Breakout

Definitions:

- Breakout Watch: Near pivot but not yet broken.
- Breakout Attempt: Intraday breakout attempt without confirmation.
- Confirmed Breakout: Close above pivot with volume confirmation.
- Failed Breakout: Previously confirmed breakout falls back below pivot.

## High Tight Flag Detection

Requirements:

- 100%+ move
- Within 4-8 weeks
- Pullback less than 25%

Classification:

- HTF Candidate
- HTF Confirmed

## Volume Analysis

Evaluate:

- Current volume
- 20-day average volume
- Up volume
- Down volume

Bullish characteristics:

- Up days have higher volume
- Pullbacks have lower volume

Ideal state:

- Demand exceeds supply

## Risk Management

Initial stop:

- Use pivot failure
- Use structure failure
- Avoid arbitrary stop levels whenever possible

Preferred:

- Structure-based stop

Example:

- Pivot = 81.4
- Entry = 82
- Stop = 79

Position management:

- At 2R: take 25% profit
- At 3R: take another 25% profit
- Remaining position: trail with trend

## Trend Exit Rules

Exit conditions:

- Failed Breakout
- Close below 50DMA
- Relative Strength deterioration
- Climax Run reversal

## Climax Run Detection

Potential Climax Run when:

- Price > 15% above 20DMA
- Or 5-day gain > 20%

Classification:

- Extended
- Climax Risk

## Timing Score

Maximum score = 100.

The score measures current setup readiness inside the approved watchlist. It does not measure company quality.

Components:

- Trend Gate: pass/fail prerequisite, not part of the score
- Setup Quality: 35 points
- Breakout Readiness: 30 points
- Volume / Demand: 20 points
- Entry Risk: 15 points

Interpretation:

- 90-100: Actionable Now / elite timing
- 80-89: Breakout Watch / strong timing
- 70-79: Constructive Base / monitor closely
- 60-69: Developing / observation only
- Below 60: Low priority unless a new trigger appears

Trend lifecycle must be tracked separately:

- Trend Age: trading days since the current trend gate began
- Days Above 50DMA: consecutive trading days above the 50DMA
- MA Stack Age: consecutive trading days with 50DMA > 150DMA > 200DMA
- Trend Phase:
  - Fresh Trend: 3-15 days
  - Developing Trend: 16-45 days
  - Mature Trend: 46-90 days
  - Late / Extended Trend: 90+ days

## Status Labels

Only use the following labels:

- Actionable Now
- Breakout Watch
- Constructive Base
- Developing Setup
- Extended / Do Not Chase
- Early Warning
- Trend Break
- Structure Break
- Repair Needed
- Data Missing

No other labels allowed.

## Daily Report Format

Reports must prioritize decision clarity over raw data tables.

Each report should include:

- Today's Core Attention
- Classification
- Focus Stock Analysis
- Full Watchlist Detail

### Classification

Use these report-level groups:

- Actionable Now: timing score 90+, valid trend, close to trigger or confirmed breakout
- Breakout Watch: timing score 80+, valid trend, near pivot and awaiting confirmation
- Constructive Base: valid trend and improving setup, but not yet actionable
- Developing Setup: trend exists but setup is early, loose, or needs more contraction
- Extended / Do Not Chase: strong momentum but poor risk/reward due to extension
- Repair Needed: trend gate failed, structure break, or entry risk is not acceptable
- Data Missing: required data unavailable

### Focus Stock Analysis

For each focus stock, include:

- Why it matters
- Today trigger
- Risk / invalidation
- Key level
- Current session context, if available

### Market Regime

QQQ:

SOXX:

SMH:

Comment:

### Top Momentum Stocks

1.
2.
3.

### Stock Analysis

Ticker:

Price:

Volume:

Relative Strength:

Trend Gate:

Trend Age:

Trend Phase:

Timing Score:

Setup Quality:

Breakout Readiness:

Volume / Demand:

Entry Risk:

Pivot:

Support:

Resistance:

Status:

Key Level Tomorrow:

Invalidation Level:

Comment:

## Alert Rules

### Alert Type 1 - Breakout

Condition:

- Close > pivot
- And volume > 1.5x average volume

### Alert Type 2 - Trend Failure

Condition:

- Close < 50DMA
- Or failed breakout

### Alert Type 3 - Climax Run

Condition:

- Price > 15% above 20DMA
- Or 5-day gain > 20%

### Alert Type 4 - Setup Readiness

Condition:

- Timing Score >= 80
- Trend Gate = Pass
- Pivot Gap between -5% and +2%
- Entry Risk is defined and acceptable

## Output Style

Keep reports concise.

Avoid storytelling.

Focus on:

- Trend
- Timing
- Trend lifecycle
- VCP contraction
- Volume
- Structure
- Risk

Always prioritize objective market behavior over narratives.

If data is unavailable:

- Mark as "Data Missing"
- Never invent information

## Current Watchlist

Core:

- INTC
- STM
- AMD
- MU
- NVDA
- BE
- TTMI
- SNDK
- MXL
- LITE
- AVGO
- CIEN

Benchmarks:

- QQQ
- SOXX
- SMH

Generate reports daily after market close.
