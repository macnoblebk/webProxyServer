import socket
import sys
from urllib.parse import urlparse
from pathlib import Path

# Default values and constants
DEFAULT_HTTP_PORT = 80
STATUS_CODE_200_OK = 200
STATUS_CODE_404_NOT_FOUND = 404
BUFFER_SIZE = 1024
CACHE_FOLDER = "cache"


def parse_request(request):
    """
        Parses the incoming HTTP request and extracts method, URL, and version.
        Args:
            request (str): The HTTP request string.
        Returns:
            tuple: A tuple containing method, URL, and version.
    """
    lines = request.split("\r\n")
    method, url, version = lines[0].split()
    if method != "GET" or version != "HTTP/1.1":
        raise ValueError("Malformed request! Usage: GET <URL> HTTP/1.1")
    return method, url, version


def parse_url(url):
    """
        Parses the URL and extracts host, port, and path.
        Args:
            url (str): The URL to parse.
        Returns:
            tuple: A tuple containing host, port, and path.
    """
    parsed_url = urlparse(url)
    host = parsed_url.hostname
    port = parsed_url.port or DEFAULT_HTTP_PORT
    path = parsed_url.path
    return host, port, path