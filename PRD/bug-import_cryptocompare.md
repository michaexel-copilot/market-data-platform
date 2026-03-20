# uv run import-cryptocompare migrate	

this process leads to different rows for the same asset. 
the source data has BTC-USD as instrument_id but instrument-id should be bitcoin.
the single source of truth comes from coinmarketcap, so a mapping from cryptocompare's id to the coinmarketcap id is necesssary.

# uv run import-cryptocompare aggregate-daily

the same as for the hourly data. 
this process could be lead to different rows for the same asset. 
the source data has BTC-USD as instrument_id but instrument-id should be bitcoin.
the single source of truth comes from coinmarketcap, so a mapping from cryptocompare's id to the coinmarketcap id is necesssary.