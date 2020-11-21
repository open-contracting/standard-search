import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from multiprocessing import Process

from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _

from default.extract_sphinx import process


class Command(BaseCommand):
    help = "crawls a directory, and prepares the data to POST to the API"

    def add_arguments(self, parser):
        parser.add_argument("directory", help=_("the directory to crawl"))
        parser.add_argument("base-url", help=_("the URL at which the directory will be deployed"))
        parser.add_argument("secret", help=_("the secret value to authenticate with the API"))

    def handle(self, *args, **options):
        host = "localhost"
        port_number = 8331

        def http_server():
            os.chdir(options["directory"])
            HTTPServer((host, port_number), SimpleHTTPRequestHandler).serve_forever()

        p = Process(target=http_server)

        data = {}
        try:
            p.start()

            for entry in os.scandir(options["directory"]):
                if not entry.is_dir():
                    continue

                language_code = entry.name

                results = process(f"http://{host}:{port_number}/{language_code}/", options["base_url"])

                data[language_code] = results
        finally:
            p.terminate()

        json.dump({"secret": options["secret"], "base_url": options["base_url"], "data": data}, sys.stdout)
