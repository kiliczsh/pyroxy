# Pyroxy

Pyroxy is a lightweight HTTP proxy server written in Python that helps bypass CORS restrictions for web applications. It provides a simple way to make cross-origin requests through a proxy server.

## Features

- Multiple request formats (raw, json, info)
- Support for all HTTP methods (GET, POST, PUT, DELETE, etc.)
- CORS headers support
- Request caching with configurable TTL
- JSONP support
- Custom charset encoding
- Response metadata
- Connection pooling
- Logging

## Installation

```bash
uv sync
source .venv/bin/activate
```

## Usage

### Starting the Server

```bash
# Start with default settings (port 1458)
uv run pyroxy

# Start with custom port and host
uv run pyroxy --port 8000 --host localhost

# Start in debug mode
uv run pyroxy --debug
```

### Making Requests

The proxy server supports several endpoints:

- `/raw` - Returns the raw response
- `/json` - Returns JSON-formatted response with metadata
- `/info` - Returns only metadata about the URL
- `/get` - Alias for /json

#### Example URLs:

```
# Get raw content
http://localhost:1458/raw?url=https://api.example.com/data

# Get JSON response with metadata
http://localhost:1458/json?url=https://api.example.com/data

# Get only page info
http://localhost:1458/info?url=https://api.example.com/data

# Use with custom charset
http://localhost:1458/raw?url=https://api.example.com/data&charset=iso-8859-1

# Disable caching
http://localhost:1458/json?url=https://api.example.com/data&disableCache=true

# Set custom cache time (in seconds)
http://localhost:1458/json?url=https://api.example.com/data&cacheMaxAge=3600

# Use JSONP
http://localhost:1458/json?url=https://api.example.com/data&callback=myFunction
```

### Query Parameters

- `url` (required) - The target URL to proxy
- `charset` - Specify character encoding (default: utf-8)
- `disableCache` - Disable caching for this request
- `cacheMaxAge` - Set custom cache duration in seconds
- `callback` - JSONP callback function name
- `format` - Response format (raw, json, info)

## Response Formats

### Raw Format
Returns the raw response from the target URL with original headers.

### JSON Format
Returns a JSON object containing:
```json
{
  "contents": "page content",
  "status": {
    "url": "requested url",
    "content_type": "response content type",
    "content_length": "response length",
    "http_code": "HTTP status code",
    "response_time": "request duration in seconds"
  }
}
```

### Info Format
Returns metadata about the URL without fetching the full content:
```json
{
  "url": "requested url",
  "content_type": "content type",
  "content_length": "content length",
  "http_code": "HTTP status code"
}
```

## Configuration

Default settings:
- Port: 1458
- Host: 0.0.0.0
- Cache Time: 60 minutes
- Minimum Cache Time: 5 minutes

## Requirements

- Python 3.13+
- Flask
- Requests

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
