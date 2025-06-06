import socket
import ssl
import re
import base64

import wbetools
import utils
from socket_manager import socket_manager
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

    def __init__(self, url):
        try:
            self.is_view_source = False
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
            response_headers[header.casefold()] = value
    
        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers

        content_length = int(response_headers.get("content-length", 0))
        content = response.read(content_length).decode('utf-8')
    
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
    
    @wbetools.js_hide
    def __repr__(self):
        return "URL(scheme={}, host={}, port={}, path={!r})".format(
            self.scheme, self.host, self.port, self.path)
