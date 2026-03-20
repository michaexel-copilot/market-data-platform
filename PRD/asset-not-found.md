# Asset not found on the source

if a service called from the scheduler returns 04 Not Found like this:
026-03-20 17:45:18,675 INFO httpx: HTTP Request: GET https://eodhd.com/api/intraday/home3?api_token=69883e7859d9d2.62439075&fmt=json&from=1774023032&to=1774024832&interval=5m "HTTP/1.1 404 Not Found"

save the information in a table and set this asset to not fetch data from the source. 

Task 1: define the table structure.
Task 2: update the fetch logic.
