import json
import os.path
from copy import deepcopy
from http.server import HTTPServer, SimpleHTTPRequestHandler
from multiprocessing import Process
from unittest.mock import patch

from django.test import TestCase

from standardsearch.extract_sphinx import extract_page, process
from standardsearch.webapp.views import _load

expected = [
    {
        "text": "\nAbout\nThe Open Contracting Data Standard",
        "title": "Open Contracting Data Standard: Documentation - About",
        "url": "https://standard.open-contracting.org/dev/en/#about",
    },
    {
        "text": "\nGuidance\nAre you new to OCDS?",
        "title": "Guidance",
        "url": "https://standard.open-contracting.org/dev/en/guidance/#guidance",
    },
    {
        "text": "\nDesign\nThis phase is about setting up your OCDS implementation to be a success.",
        "title": "Design",
        "url": "https://standard.open-contracting.org/dev/en/guidance/page/#design",
    },
    {
        "text": "\nMerging\n\nAn OCDS record …\n\n",
        "title": "Merging",
        "url": "https://standard.open-contracting.org/dev/en/schema/#merging",
    },
    {
        "text": "\nMerging specification\n\n",
        "title": "Merging - Merging specification",
        "url": "https://standard.open-contracting.org/dev/en/schema/#merging-specification",
    },
    {
        "text": "\nMerge routine\n\nTo create a compiled or versioned release, you must:\n"
        "\nGet all releases with the same ocid value\n\n",
        "title": "Merging - Merge routine",
        "url": "https://standard.open-contracting.org/dev/en/schema/#merge-routine",
    },
    {
        "text": "\nArray values\n\nIf the input array contains anything other than objects, treat the array as a "
        "literal value. Otherwise, there are two sub-routines for arrays of objects: whole list merge and "
        "identifier merge.\n\n",
        "title": "Merging - Array values",
        "url": "https://standard.open-contracting.org/dev/en/schema/#array-values",
    },
    {
        "text": "\nWhole list merge\n\nAn input array must be treated as a literal value if the corresponding field "
        'in a dereferenced copy of the release schema has "array" in its type and if any of the following are '
        "also true:\n",
        "title": "Merging - Whole list merge",
        "url": "https://standard.open-contracting.org/dev/en/schema/#whole-list-merge",
    },
]

expected_es = [
    {
        "base_url": "https://standard.open-contracting.org/dev/es/",
        "text": "\nAcerca de\nEl Estándar de Datos de Contratación Abierta",
        "title": "Estándar de Datos de Contrataciones Abiertas: Documentación - Acerca de",
        "url": "https://standard.open-contracting.org/dev/es/#about",
    }
]


class StandardSearchTestCase(TestCase):
    maxDiff = None

    def setUp(self):
        host = "localhost"
        port_number = 8332

        def http_server():
            os.chdir(os.path.join("tests", "fixtures"))
            HTTPServer((host, port_number), SimpleHTTPRequestHandler).serve_forever()

        self.process = Process(target=http_server)
        self.process.start()

    def tearDown(self):
        self.process.terminate()

    def test_extract_page(self):
        results = extract_page(
            "http://localhost:8332/en/guidance/",
            "https://standard.open-contracting.org/dev/en/guidance/",
        )

        self.assertEqual(results, ([expected[1]], "page/"))

    def test_extract_page_deep(self):
        results = extract_page(
            "http://localhost:8332/en/schema/",
            "https://standard.open-contracting.org/dev/en/schema/",
        )

        self.assertEqual(results, (expected[3:], []))

    def test_process(self):
        results = process("http://localhost:8332/en/", "https://standard.open-contracting.org/dev/en/")

        self.assertEqual(results, expected)

    @patch("standardsearch.webapp.views._load")
    def test_index(self, load):
        response = self.client.post(
            "/v1/index_ocds",
            json.dumps({
                "secret": "change_this_secret_on_production",
                "base_url": "https://standard.open-contracting.org/dev/",
                "data": {
                    "en": deepcopy(expected),
                    "es": deepcopy(expected_es),
                },
            }),
            content_type="application/json",
        )

        content = json.loads(response.content.decode("utf-8"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")
        self.assertEqual(content, {"success": True})

        self.assertEqual(
            list(map(tuple, load.mock_calls)),
            [
                (
                    "",
                    (
                        "https://standard.open-contracting.org/dev/en/",
                        expected,
                        "en",
                    ),
                    {},
                ),
                (
                    "",
                    (
                        "https://standard.open-contracting.org/dev/es/",
                        expected_es,
                        "es",
                    ),
                    {},
                ),
            ],
        )

    @patch("elasticsearch.Elasticsearch")
    def test_load(self, klass):
        es = klass.return_value
        es.indices.exists.return_value = False

        _load("https://standard.open-contracting.org/dev/en/", deepcopy(expected), "en")

        klass.assert_called_once_with()
        es.indices.exists.assert_called_once_with("standardsearch_en")
        es.indices.create.assert_called_once_with(
            body={
                "mappings": {
                    "results": {
                        "_all": {"analyzer": "english"},
                        "properties": {
                            "text": {"type": "text", "analyzer": "english"},
                            "title": {"type": "text", "analyzer": "english"},
                            "base_url": {"type": "keyword"},
                        },
                    }
                }
            },
            index="standardsearch_en",
        )
        es.delete_by_query.assert_called_once_with(
            body={
                "query": {
                    "term": {"base_url": "https://standard.open-contracting.org/dev/en/"}
                }
            },
            doc_type="results",
            index="standardsearch_en",
        )
        self.assertEqual(es.index.call_count, 8)
        self.assertEqual(
            tuple(es.index.mock_calls[0]),
            (
                "",
                (),
                {
                    "body": {
                        "base_url": "https://standard.open-contracting.org/dev/en/",
                        "text": "\nAbout\nThe Open Contracting Data Standard",
                        "title": "Open Contracting Data Standard: Documentation - About",
                        "url": "https://standard.open-contracting.org/dev/en/#about",
                    },
                    "doc_type": "results",
                    "id": "https://standard.open-contracting.org/dev/en/#about",
                    "index": "standardsearch_en",
                },
            ),
        )
