import standardsearch.etl.extract
from standardsearch.etl.sources import Source
from standardsearch.etl.load import load

from standardsearch.etl.extract_sphinx import ExtractSphinx


LANG_MAP = {'en': 'english',
            'fr': 'french',
            'es': 'spanish'}


def run_scrape(version='latest', langs=('en', 'es', 'fr'), url=None, new_url=None):

    if not url:
        url = 'http://standard.open-contracting.org/{}/'.format(version)

    for lang in langs:
        lang_url = url.rstrip('/') + '/' + lang + '/'
        new_lang_url = None
        if new_url:
            new_lang_url = new_url.rstrip('/') + '/' + lang + '/'
        extract = standardsearch.etl.extract.Extract()
        extract.add_source(Source(url=lang_url, new_url=new_lang_url, extractor=ExtractSphinx))
        extract.go()
        load(base_url=(new_lang_url or lang_url), language=LANG_MAP.get(lang, 'standard'))
