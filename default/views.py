import json
from urllib.parse import urljoin

import elasticsearch
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

LANGUAGE_MAP = {
    "en": "english",
    "es": "spanish",
    "fr": "french",
    "it": "italian",
}


def _load(base_url, results, language_code):
    es = elasticsearch.Elasticsearch()
    es_index = f"standardsearch_{language_code}"

    if not es.indices.exists(es_index):
        # https://www.elastic.co/guide/en/elasticsearch/reference/7.10/analysis-lang-analyzer.html
        language = LANGUAGE_MAP.get(language_code, "standard")

        es.indices.create(
            index=es_index,
            body={
                "mappings": {
                    "properties": {
                        "text": {"type": "text", "analyzer": language},
                        "title": {"type": "text", "analyzer": language},
                        "base_url": {"type": "keyword"},
                    },
                },
            },
        )

    es.delete_by_query(
        index=es_index,
        body={"query": {"term": {"base_url": base_url}}},
    )

    for result in results:
        result["base_url"] = base_url
        es.index(index=es_index, id=result["url"], body=result)


def _respond(content):
    response = JsonResponse(content)
    response["Access-Control-Allow-Origin"] = "*"
    return response


def search_v1(request):
    q = request.GET.get("q", "")
    base_url = request.GET.get("base_url", "")

    split = base_url.rstrip("/").split("/")
    if split:
        lang = split[-1]
    else:
        lang = None

    es_index = "standardsearch"
    if lang:
        es_index = es_index + "_" + lang

    res = elasticsearch.Elasticsearch().search(
        index=es_index,
        size=100,
        body={
            "query": {
                "bool": {
                    "must": {
                        "query_string": {
                            "query": q,
                            "fields": ["text", "title^3"],
                            "default_operator": "and",
                        },
                    },
                    "filter": {"term": {"base_url": base_url}},
                }
            },
            "highlight": {"fields": {"text": {}, "title": {}}},
        },
    )

    content = {
        "results": [],
        "count": res["hits"]["total"]["value"],
    }

    for hit in res["hits"]["hits"]:
        content["results"].append(
            {
                "title": hit["_source"]["title"],
                "url": hit["_source"]["url"],
                "highlights": hit["highlight"].get("text", hit["highlight"].get("title")),
            }
        )

    return _respond(content)


@require_POST
def index_ocds(request):
    content = json.loads(request.body.decode("utf-8"))

    if content["secret"] != settings.OCDS_SECRET:
        return _respond({"error": "secret not correct"})

    for language_code, results in content["data"].items():
        _load(urljoin(content["base_url"], f"{language_code}/"), results, language_code)

    return _respond({"success": True})
