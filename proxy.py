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


def cache_file(url, data):
    """
        Caches the HTTP response data to a file (cache/host/port/path).
        Args:
            url (str): The URL of the response.
            data (bytes): The response data to cache.
    """
    parsed_url = urlparse(url)
    cache_folder = Path(CACHE_FOLDER) / parsed_url.hostname / str(parsed_url.port) / parsed_url.path[1:]
    cache_folder.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_folder, "wb") as f:
        f.write(data)


def get_file_from_cache(url):
    """
       Retrieves data from the cache (cache/host/port/path).
       Args:
           url (str): The URL of the cached data.
       Returns:
           str or None: The cached data if found, else None.
    """
    parsed_url = urlparse(url)
    cache_folder = Path(CACHE_FOLDER) / parsed_url.hostname / str(parsed_url.port) / parsed_url.path[1:]
    if cache_folder.exists():
        with open(cache_folder, "rb") as f:
            return f.read().decode()
    return None


def handle_request(client_socket, request):
    """
        Handles incoming client requests.
        Args:
            client_socket (socket): The client socket.
            request (str): The HTTP request string.
    """
    method, url, version = parse_request(request)

    if not url:
        client_socket.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n")
        return

    host, port, path = parse_url(url)
    cached_response = get_file_from_cache(url)

    if cached_response:
        # If the response is cached, serve it from the cache
        print("Yay! The requested file is in the cache...")
        headers, _, body = cached_response.partition("\r\n\r\n")
        client_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\nCache-Hit: 1\r\n\r\n"
                              % (len(body)))
        client_socket.sendall(body.encode())

    else:
        # If not cached, forward the request to the origin server
        print("Oops! No cache hit! Requesting origin server for the file...")
        print("Sending the following message to proxy to server:")
        print(f"{method} {path} {version}\nhost: {host}\nConnection:close")

        try:
            remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_socket.connect((host, port))
            remote_socket.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
            response = b""

            # Receive the response from the origin server
            while True:
                data = remote_socket.recv(BUFFER_SIZE)
                if not data:
                    break
                response += data
            status_code = int(response.split(b" ")[1])

            if status_code == STATUS_CODE_200_OK:
                # If response status is 200, cache response
                print("Response received from server, and status code is 200! Write to cache, save time next time...")
                headers, sep, body = response.partition(b"\r\n\r\n")
                modified_headers = headers + b"\r\nCache-Hit: 0"
                client_socket.sendall(modified_headers + sep + body)
                cache_file(url, response)

            elif status_code == STATUS_CODE_404_NOT_FOUND:
                # If response status is 404, return it without caching
                print("Response received from server, but status code is not 200! No cache writing...")
                headers, sep, body = response.partition(b"\r\n\r\n")
                modified_headers = headers + b"\r\nCache-Hit: 0"
                client_socket.sendall(modified_headers + sep + body)

            else:
                # For other status codes, return 500 Internal Server Error
                headers, _, _ = response.partition(b"\r\n\r\n")
                _, *response_headers = headers.split(b"\r\n")
                header_dict = {k: v for k, v in
                               (header.split(b": ", maxsplit=1) for header in response_headers)}
                date = header_dict.get(b"Date")
                content_type = header_dict.get(b"Content-Type")
                connection = header_dict.get(b"Connection")
                client_socket.sendall(
                    b"HTTP/1.1 500 Internal Server Error\r\nCache-Hit: 0\r\nDate: %s\r\nContent-Length: "
                    b"0\r\nContent-Type:%s\r\nConnection: %s\r\n\r\n"
                    % (date, content_type, connection))

        except Exception as e:
            print("Error connecting to origin server:", e)

        finally:
            remote_socket.close()
    print("Now responding to the client...")
    print("All done! Closing socket...")
    client_socket.close()  # Close the client socket after handling the request


def proxy_server(port):
    """
        Starts the proxy server.
        Args:
            port (int): The port number to listen on.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind(("", port))
        server_socket.listen(1)
        while True:
            print("\n******************** Ready to serve ********************")
            client_socket, client_address = server_socket.accept()
            print("Received a client connection from", client_address)
            request = client_socket.recv(BUFFER_SIZE)
            print("Received a message from this client:", request)
            handle_request(client_socket, request.decode())


# Main function
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 proxy.py <port>")
        sys.exit(1)
    port = int(sys.argv[1])
    proxy_server(port)
