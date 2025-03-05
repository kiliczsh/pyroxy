#!/usr/bin/env python3
"""
Pyroxy Server
A Python implementation of Pyroxy, a service to bypass CORS restrictions
"""

import json
import time
import argparse
import logging
from urllib.parse import urlparse, parse_qs
from functools import lru_cache
from http import HTTPStatus

import requests
from flask import Flask, request, Response, jsonify

# Constants
VERSION = "1.0.0"
DEFAULT_CACHE_TIME = 60 * 60  # 60 minutes
MIN_CACHE_TIME = 5 * 60  # 5 minutes
DEFAULT_USER_AGENT = f"Mozilla/5.0 (compatible; Pyroxy-py/{VERSION}; +http://pyroxy.ai/)"

# Setup Flask app
app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('pyroxy')

# Session for HTTP requests with connection pooling
session = requests.Session()
session.headers.update({'User-Agent': DEFAULT_USER_AGENT})


class ResponseCache:
    """Simple cache decorator with time-based expiration"""
    def __init__(self, max_size=1000):
        self.cache = {}
        self.max_size = max_size

    def get(self, key):
        """Get item from cache if it exists and is not expired"""
        if key in self.cache:
            item = self.cache[key]
            if item['expiry'] > time.time():
                return item['data']
            else:
                del self.cache[key]
        return None

    def set(self, key, value, expiry_seconds):
        """Add item to cache with expiration time"""
        # Clear cache if it gets too big
        if len(self.cache) >= self.max_size:
            # Simple approach: clear entire cache when full
            self.cache = {}

        self.cache[key] = {
            'data': value,
            'expiry': time.time() + expiry_seconds
        }


# Initialize cache
response_cache = ResponseCache()


def get_page_info(url):
    """Get metadata about a page without fetching its content"""
    try:
        response = session.head(url, allow_redirects=True, timeout=10)
        return {
            "url": url,
            "content_type": response.headers.get('content-type'),
            "content_length": int(response.headers.get('content-length', -1)),
            "http_code": response.status_code
        }
    except requests.RequestException as e:
        return {"error": str(e)}


def get_raw_page(url, request_method='GET', charset=None):
    """Get the raw content of a page"""
    try:
        response = session.request(
            method=request_method,
            url=url,
            allow_redirects=True,
            timeout=10
        )

        content = response.content
        if charset and charset.lower() != 'utf-8':
            try:
                content = response.content.decode(charset).encode('utf-8')
            except UnicodeError:
                pass  # If decoding fails, use the original content

        return {
            "content": content,
            "contentType": response.headers.get('content-type'),
            "contentLength": len(content)
        }
    except requests.RequestException as e:
        return {"error": str(e)}


def get_page_contents(url, request_method='GET', charset=None):
    """Get page contents with metadata"""
    try:
        response = session.request(
            method=request_method,
            url=url,
            allow_redirects=True,
            timeout=10
        )

        content = response.content
        if charset:
            try:
                content = content.decode(charset)
            except UnicodeError:
                content = content.decode('utf-8', errors='replace')
        else:
            content = content.decode('utf-8', errors='replace')

        return {
            "contents": content,
            "status": {
                "url": url,
                "content_type": response.headers.get('content-type'),
                "content_length": len(response.content),
                "http_code": response.status_code
            }
        }
    except requests.RequestException as e:
        return {
            "contents": None,
            "status": {"error": str(e)}
        }


def get_page(params):
    """Process a page request based on the format requested"""
    url = params.get("url")
    fmt = params.get("format", "json").lower()
    request_method = params.get("requestMethod", "GET")
    charset = params.get("charset")

    if fmt == "info" or request_method == "HEAD":
        return get_page_info(url)
    elif fmt == "raw":
        return get_raw_page(url, request_method, charset)
    else:
        return get_page_contents(url, request_method, charset)


def process_request(fmt):
    """Process the incoming proxy request"""
    start_time = time.time()

    # Parse parameters
    params = request.args.to_dict()
    params["format"] = fmt
    params["requestMethod"] = request.method

    if request.method == "OPTIONS":
        return ""

    if "url" not in params:
        return jsonify({"error": "No URL provided. Please add a url parameter."}), 400

    # Create cache key
    cache_key = f"{params['requestMethod']}:{params['url']}:{fmt}:{params.get('charset', '')}"

    # Check cache
    if request.method in ["GET", "HEAD"] and not params.get("disableCache") == "true":
        cached_response = response_cache.get(cache_key)
        if cached_response:
            return create_response(cached_response, params, start_time)

    # Fetch the page
    page = get_page(params)

    # Create response
    response = create_response(page, params, start_time)

    # Cache the response if it's a GET or HEAD request
    if request.method in ["GET", "HEAD"] and not params.get("disableCache") == "true":
        max_age = max(
            MIN_CACHE_TIME,
            int(params.get("cacheMaxAge", DEFAULT_CACHE_TIME))
        )
        response_cache.set(cache_key, page, max_age)

    # Log request
    log_request(request, params, page, start_time)

    return response


def create_response(page, params, start_time):
    """Create the appropriate response based on the format and results"""
    fmt = params.get("format")

    # Set cache headers for GET and HEAD requests
    response_headers = {}
    if request.method in ["GET", "HEAD"]:
        max_age = 0 if params.get("disableCache") == "true" else max(
            MIN_CACHE_TIME,
            int(params.get("cacheMaxAge", DEFAULT_CACHE_TIME))
        )
        response_headers["Cache-Control"] = f"public, max-age={max_age}, stale-if-error=600"

    # Add Via header
    response_headers["Via"] = f"pyroxy-py v{VERSION}"

    # Process raw format differently
    if fmt == "raw" and not page.get("error"):
        response_headers.update({
            "Content-Length": str(page.get("contentLength", 0)),
            "Content-Type": page.get("contentType", "text/plain")
        })
        return Response(
            page.get("content", b""),
            headers=response_headers
        )

    # Add response time to the result
    response_time = time.time() - start_time
    if "status" in page:
        page["status"]["response_time"] = response_time
    else:
        page["response_time"] = response_time

    # Set content type for JSON responses
    response_headers["Content-Type"] = f"application/json; charset={params.get('charset', 'utf-8')}"

    # Handle JSONP callback
    callback = params.get("callback")
    if callback:
        # Create JSONP response
        body = f"{callback}({json.dumps(page)});"
        return Response(
            body,
            headers=response_headers,
            mimetype="application/javascript"
        )

    # Regular JSON response
    return Response(
        json.dumps(page),
        headers=response_headers,
        mimetype="application/json"
    )


def log_request(req, params, page, start_time):
    """Log the processed request"""
    if logger.level > logging.INFO:
        return

    try:
        to_url = urlparse(params.get("url", ""))
        from_url = None
        if "Origin" in req.headers:
            from_url = urlparse(req.headers.get("Origin"))

        status = page.get("status", {})
        if isinstance(status, dict) and "error" in status:
            error = status.get("error")
            logger.warning(f"Error: {error} - URL: {params.get('url')}")

        logger.info(
            f"{req.method} - {params.get('format')} - "
            f"From: {from_url.hostname if from_url else 'browser'} - "
            f"To: {to_url.hostname if to_url else 'unknown'} - "
            f"Time: {time.time() - start_time:.3f}s"
        )
    except Exception as e:
        logger.error(f"Error logging request: {e}")


@app.route('/<format>', methods=['GET', 'POST', 'HEAD', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
def handle_request(format):
    """Route handler for all formats"""
    if format not in ['get', 'raw', 'json', 'info']:
        return jsonify({"error": "Invalid format. Use one of: get, raw, json, info"}), 400
    return process_request(format)


@app.after_request
def add_cors_headers(response):
    """Add CORS headers to every response"""
    origin = request.headers.get('Origin', '*')
    response.headers.update({
        'Access-Control-Allow-Origin': origin,
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Allow-Headers': 'Origin, X-Requested-With, Content-Type, Content-Encoding, Accept',
        'Access-Control-Allow-Methods': 'OPTIONS, GET, POST, PATCH, PUT, DELETE'
    })
    return response


def main():
    """Main entry point for the application"""
    parser = argparse.ArgumentParser(description='pyroxy Python Proxy Server')
    parser.add_argument('--port', type=int, default=1458, help='Port to run the server on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind the server to')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()

    print(f"Starting pyroxy-py v{VERSION}")
    print(f"Listening on http://{args.host}:{args.port}/raw?url=https://www.github.com")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
