add a button to the main segmented button list after fundamentals:
name: place order
add a place order form with all necessary items:
- Margin (Cross / Isolated) default: cross
- Position (Buy/Long - Sell/Short) default Sell/Short
- Leverage (Slider 1x to 10 ) default 2x (Short). 1x (Long)
- Position (Market / Limit) Default market
- Size (Field for Price 2 decimal numbers)
- Risk Management
    - Reduce only
    - Take Profilt Stop /Loss ( default)
    - Field s for TP price (default: 30 day ATH) and Gain (%) automatically calculated
    - Fields for SL Price (default: 30 day ATL) and  Loss (%) automatically calculated
- Show the levered max profit and loss if it differs from Gain % or Loss % from above
- Place an order button. After pressing the place roder button show a confirmation box with all relevant data for the trade. Button Confirm -> Plac the order, Button Cancel -> Close the Dialog and do not place the order

- Use Testnet as default. Let me switch to main net. If mainnet is chosen draw a thick red frame at the form.

Use the existing API-Client for Hyperliquid: pc2-mint:/work/projekte/hyperliquid-python

Do not assume anything. Ask me for any decision you have to make.

