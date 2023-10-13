import mimetypes
import pathlib
import threading
import socket
import json
import logging
import os
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib import parse
from time import sleep
from datetime import datetime
from pkg_resources import resource_filename


logger = logging.getLogger('simple_example')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)    


def output_logging_message(message: str, ip: str = ""):
    date_now = datetime.now().strftime("%d/%b/%Y %H:%M:%S")
    if ip:
        logger.debug(f"{ip} - - [{date_now}] {message}")
    else:
        logger.debug(f"[{date_now}] {message}")


def get_connection_settings(server: str, get_alias: bool = False) -> tuple:
    with open(resource_filename("webhw04", "./settings/connection.json"), "r") as fh:
        settings = json.load(fh)
        if get_alias:
            return settings.get(server).get("address"), settings.get(server).get("port"), settings.get(server).get("alias")
        else:
            return settings.get(server).get("address"), settings.get(server).get("port")


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pr_url = parse.urlparse(self.path)
        if pr_url.path == "/":
            self.send_html_file("index.html")
        elif pr_url.path == "/message":
            self.send_html_file("message.html")
        elif pr_url.path == "/shutdown":
            self.send_data(b"")
            self.server.running = False
        else:
            if pathlib.Path().joinpath(resource_filename("webhw04", pr_url.path[1:])).exists():
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
            if data:
                output_logging_message(f"Send data: {data} to {server_address}", server_address[0])


class MainServer:
    def __init__(self) -> None:
        self._server_address = get_connection_settings("http_server")
        self._server = HTTPServer(self._server_address, HttpHandler)
        self._thread = threading.Thread(target=self.run)

    def run(self) -> None:
        self._server.running = True
        while self._server.running:
            self._server.handle_request()
        output_logging_message(f"HTTP server stoped by handler")

    def start(self) -> None:
        self._thread.start()


class MinorServer:
    def __init__(self) -> None:
        self._server_address = get_connection_settings("socket_server")
        self._thread = threading.Thread(target=self.run)

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(self._server_address)
            while True:
                data, address = sock.recvfrom(1024)
                if not data:
                    output_logging_message(f"Socket server stoped by handler")
                    break
                output_logging_message(f"Receive data: {data} from {address}", self._server_address[0])
                self.write_data_to_json(data, self._server_address[0])

    def start(self) -> None:
        self._thread.start()

    def write_data_to_json(self, data: bytes, ip: str) -> None:
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
            output_logging_message(f"Write data to file: {storage_path}", ip)


def send_shutdown_request():
    settings = get_connection_settings("http_server", True)
    try:
        requests.get(f"http://{settings[2]}:{settings[1]}/shutdown")
    except:
        pass


def run():
    logging.getLogger("http").setLevel(logging.DEBUG)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    http = MainServer()
    serv = MinorServer()

    serv.start()
    http.start()

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        output_logging_message("Programm finished by admin")
        send_shutdown_request()



if __name__ == "__main__":
    run()
