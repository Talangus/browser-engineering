import socket
import ssl

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