import socket
import ssl
import re
import base64

import utils
from socket_manager import socket_manager
from cache import cache
class URL:
    DEFAULT_FILE_PATH="file:///Users/li016390/test.html"
    SUPPORTED_SCHEME_PORTS={
        "http": 80,
        "https": 443, 
        "file": None, 
        "data":None,
        "view-source": None
        }
    DATA_URL_TYPES=["text"]
    MAX_REDIR_COUNT=5

    def __init__(self, url):
        try:
            self.is_view_source = False
            self.redirect_count = 0
            self.in_cache = False

            self.scheme, url = self.split_on_scheme(url)
            
            if self.scheme == 'data':
                self.data = url
                return
            elif self.scheme == "view-source":
                self.is_view_source = True
                self.scheme, url = self.split_on_scheme(url)

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
            print("Malformed URL found, falling back to the WBE home page.")
            print("  URL was: " + url)
            self.__init__("https://browser.engineering")

    def request(self):
        if not self.need_socket():
            if self.in_cache:
                return cache.get(str(self))
            if self.scheme == "file":
                content = utils.read_file(self.host + self.path)
                return content
            elif self.scheme =="data":
                content = self.process_data_scheme(self.data)
                return content

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
    
        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers

        if self.is_redirect_status(status):
            return self.get_redir_content(response_headers)

        content_length = int(response_headers.get("content-length", 0))
        content = response.read(content_length).decode('utf-8')
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
            "Accept": "*/*"
        }
    
    def need_socket(self):
        if cache.in_cache(str(self)):
            self.in_cache = True
            return False
        return self.scheme in ["http", "https"]
    
    def split_on_scheme(self, url_str):
        scheme, rest = url_str.split(":", 1)
        assert scheme in self.SUPPORTED_SCHEME_PORTS

        if not scheme in ['data', 'view-source']:
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
        


    def __repr__(self):
        return "URL(scheme={}, host={}, port={}, path={!r})".format(
            self.scheme, self.host, self.port, self.path)
