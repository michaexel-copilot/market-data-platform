# redesign-backtesting-v2

- [ ] remove the already existing logic and all gui elements under the accordeon #heading-strategy-controls

Now i want a backtest for several different approaches. THe goal is to find the best parameters for the chosen asset and the chosen indicator.

Now put the following input items in the accordeon: 
- [ ] add two lists of known indicators. use an endpoint for this. define the following:
    - [ ] Price (default value for Indicator 1, use the 1 hour or the 1 day data which better suits the case)
    - [ ] Simple Moving Average (default range: 1d to 200d, default value for Indicator 2)
    - [ ] EMA  (default range: 1d to 200d)
- [ ] add a Exposure list. also use an endpoint for this. define the following:
    - [ ] Long+Cash: Go Long, when <Indicator1> crosses above <Indicator2>. Hold the position for at least 1 day. Ignore any signals for the next 24 hours. After the holding period sell the position when <Indicator1> crosses below <Indicator2> and hold the usd. 
    - [ ] Short+Cash: Go short when <Indicator1> crosses below <Indicator2>. Hold the position for at least 1 day. Ignore any signals for the next 24 hours. After the holding period sell the position when <Indicator1> crosses above <Indicator2> and hold the usd.
    - [ ] Long+Short: combine the above exposures.
- add a button "Run Backtest" that iterates over the range of the indicators and find the best parameters with the biggest net profit. Plot this values, store them in the database as cache, make the cache invalidatable. 
For the backtest use the follwoing time ranges. Let the user adjust them:
1. Use the data from 31.12.2024 back to the oldest available data as test data
2. Use the data from 01.01.2025 to the most current data as validation data.
Calculate the best Parameters for the chosen Indicators show the profit and loss in both directions and show all trades in the validation time period. 
Improve the backtestimg strategy if necessary but ask me for permision
Use backtesting.py for calculationg the backtests.

## Step 1
[ ] /clear # clears the context window
[ ] /opsx-propose redesign-backtesting-v2

### Rückfragen KI (Claude Sonnet 4.6)
[ ] $rueckfragen von ki$

### Review
[ ] Review Proposal durchgeführt.
[ ] Alle Aspekte berücksichtigt

## Step 2
[ ] /opsx-apply

## Step 3 archive
[ ] /opsx-archive redesign-backtesting-v2
[ ] update documentation

## Step 4 Nacharbeiten
[ ] Review aller Tasks aus Step 0

[ ] git commit mit passendem Kommentar # manuell

## Step 5 Definition of Done

[ ] Alle Workflow Schritte durchlaufen:
[ ] Review durchgeführt
[ ] git commit mit passendem Kommentar # manuell
[ ] Dokumentation aktualisiert 
[ ] FAQ ergänzt



