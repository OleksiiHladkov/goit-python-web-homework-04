from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib import parse
from time import sleep
import mimetypes
import pathlib
import threading
import socket
import json


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pr_url = parse.urlparse(self.path)
        if pr_url.path == '/':
            self.send_html_file('index.html')
        elif pr_url.path == '/message':
            self.send_html_file('message.html')
        else:
            if pathlib.Path().joinpath(pr_url.path[1:]).exists():
                self.send_static()
            else:
                self.send_html_file('error.html', 404)
    
    def do_POST(self):
        data = self.rfile.read(int(self.headers['Content-Length']))
        self.send_data(data)
        self.send_response(302)
        self.send_header('Location', '/')
        self.end_headers()

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open(filename, 'rb') as fd:
            self.wfile.write(fd.read())

    def send_static(self):
        self.send_response(200)
        mt = mimetypes.guess_type(self.path)
        if mt:
            self.send_header("Content-type", mt[0])
        else:
            self.send_header("Content-type", 'text/plain')
        self.end_headers()
        with open(f'.{self.path}', 'rb') as file:
            self.wfile.write(file.read())

    def send_data(self, data):
        while True:
            with socket.socket() as s:
                try:
                    s.connect(get_connection_settings("socket_server"))
                    s.sendall(data)
                    break
                except ConnectionRefusedError:
                    sleep(0.5)


def get_connection_settings(server: str) -> tuple:
    with open("./settings/connection.json", 'rb') as fh:
        settings = json.load(fh)
        return settings.get(server).get("address"), settings.get(server).get("port")


def run_http(server_class=HTTPServer, handler_class=HttpHandler):
    server_address = get_connection_settings("http_server")
    http = server_class(server_address, handler_class)
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        http.server_close()


def run_socket():
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(get_connection_settings("socket_server"))
        s.listen(1)
        conn, addr = s.accept()
        print(f"Connected by {addr}")
        with conn:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                print(f'From http: {data}')


def run():
    http = threading.Thread(target=run_http)
    serv = threading.Thread(target=run_socket)

    serv.start()
    http.start()

    serv.join()
    http.join()




if __name__ == '__main__':
    run()