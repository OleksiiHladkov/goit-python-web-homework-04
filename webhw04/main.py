from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib import parse
from time import sleep
from datetime import datetime
from pkg_resources import resource_filename
import mimetypes
import pathlib
import threading
import socket
import json
import logging
import os


def output_logging_message(ip: str, message: str):
    date_now = datetime.now().strftime("%d/%b/%Y %H:%M:%S")
    logging.debug(f"{ip} - - [{date_now}] {message}")


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pr_url = parse.urlparse(self.path)
        if pr_url.path == "/":
            self.send_html_file("index.html")
        elif pr_url.path == "/message":
            self.send_html_file("message.html")
        else:
            if (
                pathlib.Path()
                .joinpath(resource_filename("webhw04", pr_url.path[1:]))
                .exists()
            ):
                self.send_static()
            else:
                self.send_html_file("error.html", 404)

    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_data(data)
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open(resource_filename("webhw04", filename), "rb") as fd:
            self.wfile.write(fd.read())

    def send_static(self):
        self.send_response(200)
        mt = mimetypes.guess_type(self.path)
        if mt:
            self.send_header("Content-type", mt[0])
        else:
            self.send_header("Content-type", "text/plain")
        self.end_headers()
        with open(resource_filename("webhw04", self.path), "rb") as file:
            self.wfile.write(file.read())

    def send_data(self, data):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            server_address = get_connection_settings("socket_server")
            sock.sendto(data, server_address)
            output_logging_message(
                server_address[0], f"Send data: {data} to {server_address}"
            )


def get_connection_settings(server: str) -> tuple:
    with open(resource_filename("webhw04", "./settings/connection.json"), "r") as fh:
        settings = json.load(fh)
        return settings.get(server).get("address"), settings.get(server).get("port")


def run_http_server(server_class=HTTPServer, handler_class=HttpHandler):
    server_address = get_connection_settings("http_server")
    http = server_class(server_address, handler_class)
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        http.server_close()


def write_data_to_json(data: bytes, ip: str):
    data_parse = parse.unquote_plus(data.decode())
    data_dict = {
        key: value for key, value in [el.split("=") for el in data_parse.split("&")]
    }
    storage_path = "./storage/data.json"

    result_dict = dict()

    if (
        pathlib.Path(resource_filename("webhw04", storage_path)).exists()
        and os.stat(resource_filename("webhw04", storage_path)).st_size
    ):
        with open(resource_filename("webhw04", storage_path), "r") as fh:
            result_dict = json.load(fh)

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    result_dict[date_str] = data_dict

    with open(resource_filename("webhw04", storage_path), "w") as fh:
        json.dump(result_dict, fh)
        output_logging_message(ip, f"Write data to file: {storage_path}")


def run_socket_server():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        server_address = get_connection_settings("socket_server")
        sock.bind(server_address)
        while True:
            data, address = sock.recvfrom(1024)
            output_logging_message(
                server_address[0], f"Receive data: {data} from {address}"
            )
            write_data_to_json(data, server_address[0])


def run():
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    http = threading.Thread(target=run_http_server, daemon=True)
    serv = threading.Thread(target=run_socket_server, daemon=True)

    serv.start()
    http.start()

    try:
        while True:
            sleep(5)
    except KeyboardInterrupt:
        output_logging_message("none", "Programm finished by user")


if __name__ == "__main__":
    run()
