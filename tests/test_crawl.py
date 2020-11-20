import json
import os.path
from copy import deepcopy
from unittest.mock import patch
from urllib.parse import urlparse

from django.test import TestCase

from standardsearch.extract_sphinx import extract_page, process
from standardsearch.webapp.views import _load

expected = [
    {
        "base_url": "https://standard.open-contracting.org/dev/en/",
        "text": "\n\n\nAbout\nThe Open Contracting Data Standard",
        "title": "Open Contracting Data Standard: Documentation - About",
        "url": "https://standard.open-contracting.org/dev/en/#about",
    },
    {
        "base_url": "https://standard.open-contracting.org/dev/en/",
        "text": "\nGuidance\nAre you new to OCDS?",
        "title": "Guidance",
        "url": "https://standard.open-contracting.org/dev/en/guidance/#guidance",
    },
    {
        "base_url": "https://standard.open-contracting.org/dev/en/",
        "text": "\nDesign\nThis phase is about setting up your OCDS implementation to be a success.",
        "title": "Design",
        "url": "https://standard.open-contracting.org/dev/en/guidance/page/#design",
    },
    {
        "base_url": "https://standard.open-contracting.org/dev/en/",
        "text": "\nMerging\n\nAn OCDS record …\n\n",
        "title": "Merging",
        "url": "https://standard.open-contracting.org/dev/en/schema/#merging",
    },
    {
        "base_url": "https://standard.open-contracting.org/dev/en/",
        "text": "\nMerging specification\n\n",
        "title": "Merging - Merging specification",
        "url": "https://standard.open-contracting.org/dev/en/schema/#merging-specification",
    },
    {
        "base_url": "https://standard.open-contracting.org/dev/en/",
        "text": "\nMerge routine\n\nTo create a compiled or versioned release, you must:\n"
        "\nGet all releases with the same ocid value\n\n",
        "title": "Merging - Merge routine",
        "url": "https://standard.open-contracting.org/dev/en/schema/#merge-routine",
    },
    {
        "base_url": "https://standard.open-contracting.org/dev/en/",
        "text": "\nArray values\n\nIf the input array contains anything other than objects, treat the array as a "
        "literal value. Otherwise, there are two sub-routines for arrays of objects: whole list merge and "
        "identifier merge.\n\n",
        "title": "Merging - Array values",
        "url": "https://standard.open-contracting.org/dev/en/schema/#array-values",
    },
    {
        "base_url": "https://standard.open-contracting.org/dev/en/",
        "text": "\nWhole list merge\n\nAn input array must be treated as a literal value if the corresponding field "
        'in a dereferenced copy of the release schema has "array" in its type and if any of the following are '
        "also true:\n",
        "title": "Merging - Whole list merge",
        "url": "https://standard.open-contracting.org/dev/en/schema/#whole-list-merge",
    },
]


def requests_get(url):
    class MockResponse:
        def __init__(self, url):
            self.url = url

        @property
        def text(self):
            components = urlparse(url).path.split("/")
            with open(
                os.path.join("tests", "fixtures", *components, "index.html")
            ) as f:
                return f.read()

        def raise_for_status(self):
            pass

    return MockResponse(url)


class StandardSearchTestCase(TestCase):
    maxDiff = None

    @patch("requests.get", side_effect=requests_get)
    def test_extract_page(self, get):
        results = extract_page(
            "https://standard.open-contracting.org/dev/en/guidance/",
            "https://standard.open-contracting.org/dev/en/",
            None,
        )

        self.assertEqual(results, ([expected[1]], "page/"))

    @patch("requests.get", side_effect=requests_get)
    def test_extract_page_deep(self, get):
        results = extract_page(
            "https://standard.open-contracting.org/dev/en/schema/",
            "https://standard.open-contracting.org/dev/en/",
            None,
        )

        self.assertEqual(results, (expected[3:], None))

    @patch("requests.get", side_effect=requests_get)
    def test_process(self, get):
        results = process("https://standard.open-contracting.org/dev/en/", None)

        self.assertEqual(results, expected)

    @patch("standardsearch.webapp.views._load")
    @patch("requests.get", side_effect=requests_get)
    def test_index(self, get, load):
        response = self.client.get(
            "/v1/index_ocds",
            {
                "secret": "change_this_secret_on_production",
                "version": "dev",
                "langs": "en,es",
            },
        )

        content = json.loads(response.content.decode("utf-8"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")
        self.assertEqual(content, {"success": True})

        self.assertEqual(
            load.mock_calls,
            [
                (
                    "",
                    (
                        "english",
                        "https://standard.open-contracting.org/dev/en/",
                        expected,
                        "en",
                    ),
                    {},
                ),
                (
                    "",
                    (
                        "spanish",
                        "https://standard.open-contracting.org/dev/es/",
                        [
                            {
                                "base_url": "https://standard.open-contracting.org/dev/es/",
                                "text": "\nAcerca de\nEl Estándar de Datos de Contratación Abierta",
                                "title": "Estándar de Datos de Contrataciones Abiertas: Documentación - Acerca de",
                                "url": "https://standard.open-contracting.org/dev/es/#about",
                            }
                        ],
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

        _load(
            "english",
            "https://standard.open-contracting.org/dev/en/",
            deepcopy(expected),
            "en",
        )

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
                    "term": {"base_url": "http://standard.open-contracting.org/dev/en/"}
                }
            },
            doc_type="results",
            index="standardsearch_en",
        )
        self.assertEqual(es.index.call_count, 8)
        self.assertEqual(
            es.index.mock_calls[0],
            (
                "",
                (),
                {
                    "body": {
                        "base_url": "http://standard.open-contracting.org/dev/en/",
                        "text": "\n\n\nAbout\nThe Open Contracting Data Standard",
                        "title": "Open Contracting Data Standard: Documentation - About",
                        "url": "https://standard.open-contracting.org/dev/en/#about",
                    },
                    "doc_type": "results",
                    "id": "https://standard.open-contracting.org/dev/en/#about",
                    "index": "standardsearch_en",
                },
            ),
        )
