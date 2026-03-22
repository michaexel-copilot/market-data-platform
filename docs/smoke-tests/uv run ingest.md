# CLI
uv run ingest-now --interval 1h --connector eodhd --symbol BTC

# REST
curl -X POST http://localhost:8010/v1/admin/run-ingest \
  -H 'Content-Type: application/json' \
  -d '{"interval":"1h","connector":"eodhd","symbol":"BTC"}'