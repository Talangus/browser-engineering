"""
This file compiles the code in Web Browser Engineering,
up to and including Chapter 1 (Downloading Web Pages),
Including exercises implemented by Tal Langus.
"""
import sys
import socket
import ssl
import os
import hashlib
import time
import re
import base64
import gzip
import wbetools

def read_file(path):
    with open(path, 'r') as file:
            content = file.read()
            return content

def html_unescape(entity):
    entity_map = {
        "&lt;": "<",
        "&gt;": ">",
        "&amp;": "&",
        "&quot;": "\"",
        "&apos;": "'",
        "&nbsp;": " ",
        "&copy;": "©",
        "&reg;": "®",
        "&trade;": "™",
        "&euro;": "€",
        "&ndash;": "–",
        "&shy;": "\u00AD"
    }
    return entity_map.get(entity, entity)

class Cache:
    def __init__(self, cache_dir="cached_data"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, key):
        hashed_key = hashlib.sha256(key.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, hashed_key)

    def set(self, key, data, max_age=None):
        cache_path = self._get_cache_path(key)
        metadata = {
            "timestamp": time.time(),
            "max_age": max_age,
        }
        with open(cache_path, "wb") as f:
            f.write(f"{metadata}\n".encode('utf-8'))
            f.write(data)

    def get(self, key):
        cache_path = self._get_cache_path(key)
        if not os.path.exists(cache_path):
            return None

        with open(cache_path, "rb") as f:
            metadata_line = f.readline().decode('utf-8').strip()
            metadata = eval(metadata_line)
            if metadata.get("max_age") is not None:
                age = time.time() - metadata["timestamp"]
                if age > metadata["max_age"]:
                    os.remove(cache_path)
                    return None

            return f.read()

    def in_cache(self, key):
        cache_path = self._get_cache_path(key)
        if not os.path.exists(cache_path):
            return False

        with open(cache_path, "rb") as f:
            metadata_line = f.readline().decode('utf-8').strip()
            metadata = eval(metadata_line)
            if metadata.get("max_age") is not None:
                age = time.time() - metadata["timestamp"]
                if age > metadata["max_age"]:
                    os.remove(cache_path)
                    return False
            return True
cache = Cache()

class SocketManager:
    def __init__(self):
        self.connections = {}  

    def get_socket(self, host, port, scheme="http"):
        key = (host, port, scheme)
        if key in self.connections:
            return self.connections[key]  
        else:
            s = socket.socket(
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
            if scheme == "https":
                ctx = ssl.create_default_context()
                s = ctx.wrap_socket(s, server_hostname=host)
            s.connect((host, port))
            self.connections[key] = s
            return s

    def send_request(self, host, port, request, scheme="http"):
        """Send an HTTP or HTTPS request and read the response."""
        s = self.get_socket(host, port, scheme)

        # Send the HTTP request
        s.sendall(request.encode('utf-8'))

        # Read the response
        response = s.makefile("rb")  # Use "rb" mode for binary reading
        headers = []
        while True:
            line = response.readline().decode('utf-8').strip()
            if not line:
                break
            headers.append(line)

        # Parse headers
        header_dict = {}
        for header in headers:
            if ": " in header:
                key, value = header.split(": ", 1)
                header_dict[key.lower()] = value

        # Read the body using Content-Length
        content_length = int(header_dict.get("content-length", 0))
        body = response.read(content_length).decode('utf-8')

        return headers, body

    def close(self):
        for s in self.connections.values():
            s.close()
        self.connections.clear()
socket_manager = SocketManager()

class URL:
    DEFAULT_FILE_PATH="file:///Users/li016390/test.html"
    SUPPORTED_SCHEME_PORTS={
        "http": 80,
        "https": 443, 
        "file": None, 
        "data":None,
        "view-source": None,
        "about": None
    }
    DATA_URL_TYPES=["text"]
    MAX_REDIR_COUNT=5

    def __init__(self, url):
        try:
            self.is_view_source = False
            self.redirect_count = 0
            self.in_cache = False
            self.is_blank = False

            self.scheme, url = self.split_on_scheme(url)

            if self.scheme == 'data':
                self.data = url
                return
            elif self.scheme == "view-source":
                self.is_view_source = True
                self.scheme, url = self.split_on_scheme(url)
            elif self.scheme == "about":
                if url == "blank":
                    self.is_blank = True
                    return
                else:
                    raise ValueError("Invalid about URL: {}".format(url))

            if "/" not in url:
                url = url + "/"
            self.host, url = url.split("/", 1)
            self.path = "/" + url

            if self.scheme == "http":
                self.port = 80
            elif self.scheme == "https":
                self.port = 443

            if ":" in self.host:
                self.host, port = self.host.split(":", 1)
                self.port = int(port)
        except:
            print("Malformed URL found")
            print("  URL was: " + url)
            self.__init__("about:blank")

    def request(self):
        if not self.need_socket():
            if self.in_cache:
                return cache.get(str(self))
            if self.scheme == "file":
                content = read_file(self.host + self.path)
                return content
            elif self.scheme =="data":
                content = self.process_data_scheme(self.data)
                return content
            elif self.is_blank:
                return ""

        s = socket_manager.get_socket(self.host, self.port, self.scheme)

        request = "GET {} HTTP/1.1\r\n".format(self.path)
        request += self.get_req_headers_string()
        request += "\r\n"

        s.send(request.encode("utf8"))
        response = s.makefile("rb")

        statusline = response.readline().decode('utf-8').strip()
        version, status, explanation = statusline.split(" ", 2)

        response_headers = {}
        while True:
            line = response.readline().decode('utf-8').strip()
            if not line: break
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()

        if self.is_redirect_status(status):
            return self.get_redir_content(response_headers)

        transfer_encoding = response_headers.get("transfer-encoding", "").casefold()
        content_encoding = response_headers.get("content-encoding", "").casefold()

        if transfer_encoding == "chunked":
            content = self.read_chunked_body(response)
        else:
            content_length = int(response_headers.get("content-length", 0))
            content = response.read(content_length)

        if content_encoding == "gzip":
            content = gzip.decompress(content)

        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            pass

        max_age =self.get_max_age(response_headers)
        if max_age:
            cache.set(str(self), content,  max_age)

        return content

    def get_req_headers_string(self):
        headers = ""
        for key,value in self.get_req_headers().items():
            headers += "{}: {}\r\n".format(key, value)
        return headers

    def get_req_headers(self):
        return {
            "Host": self.host,
            "Connection": "keep-alive",
            "User-Agent":"Tal_browser",
            "Accept": "*/*",
            "Accept-Encoding": "gzip"
        }

    def need_socket(self):
        if cache.in_cache(str(self)):
            self.in_cache = True
            return False
        return self.scheme in ["http", "https"]

    def split_on_scheme(self, url_str):
        scheme, rest = url_str.split(":", 1)
        assert scheme in self.SUPPORTED_SCHEME_PORTS

        if not scheme in ['data', 'view-source', 'about']:
            rest = rest[2:]

        return scheme, rest

    def process_data_scheme(self, rest):
        data_is_base64 = False
        type_and_encoding, data = rest.split(',', 1)

        if ';' in type_and_encoding:
            media_type, encoding = type_and_encoding.split(';')
            if encoding == 'base64':
                data_is_base64 = True
        else:
            media_type = type_and_encoding

        if media_type == '':
            data_type = "text"
            data_subtype = "plain"
        else:
            data_type, data_subtype = media_type.split("/", 1)

        if data_type not in self.DATA_URL_TYPES:
            raise ValueError(f"Invalid data type: {data_type}")

        if data_is_base64:
            decoded_bytes = base64.b64decode(data)
            data = decoded_bytes.decode('utf-8')

        return data

    def get_redir_content(self, response_headers):
        if "location" not in response_headers:
            raise Exception("Missing location header in 300 response")

        self.redirect_count += 1
        if self.redirect_count > self.MAX_REDIR_COUNT:
            raise Exception("Too many redirects")

        location = response_headers["location"]
        if self.is_relative_location(location):
            self.path = location
            return self.request()
        else:
            new_url = URL(location)
            new_url.redirect_count = self.redirect_count
            return new_url.request()

    def read_chunked_body(self, response):
        chunks = []
        while True:
            line = response.readline().decode("utf-8").strip()
            if not line:
                break

            chunk_size = int(line, 16)  
            if chunk_size == 0:
                break  

            chunk = response.read(chunk_size)
            chunks.append(chunk)
            response.read(2)

        return b"".join(chunks)

    @staticmethod
    def is_redirect_status(status):
        return status.startswith('3')

    @staticmethod
    def is_relative_location(location):
        return location.startswith('/')

    @staticmethod
    def get_max_age(response_headers):
        cache_control = response_headers.get("cache-control", "")
        if not cache_control:
            return 0

        directives = cache_control.split(",")
        max_age = None
        valid_directives = {"max-age", "no-store"}

        for directive in directives:
            directive = directive.strip()
            if directive.startswith("max-age="):
                try:
                    max_age = int(directive.split("=", 1)[1])
                except ValueError:
                    return 0  
            elif directive == "no-store":
                return 0  
            elif directive.split("=")[0].strip() not in valid_directives:
                return 0  

        return max_age if max_age is not None else 0
    @wbetools.js_hide
    def __repr__(self):
        return "URL(scheme={}, host={}, port={}, path={!r})".format(
        getattr(self, "scheme", None),
        getattr(self, "host", None),
        getattr(self, "port", None),
        getattr(self, "path", None)
    )

def show(body):
    in_tag = False
    entity_buffer = ""
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif c == "&" and not in_tag:
            entity_buffer = "&"
        elif entity_buffer:
            entity_buffer += c
            if c == ";":
                entity = "".join(entity_buffer)
                print(html_unescape(entity), end="")
                entity_buffer = ""
        elif not in_tag:
            print(c, end="")

def load(url):
    body = url.request()
    if url.is_view_source:
        print(body)
    else:
        show(body)

def get_url_arg():
    if len(sys.argv) > 1:
        return sys.argv[1]
    else:
        return URL.DEFAULT_FILE_PATH

if __name__ == "__main__":
    url_arg = get_url_arg()
    url = URL(url_arg)
    load(url)
    socket_manager.close()
