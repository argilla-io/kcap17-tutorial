import spacy
from spacy.tokens import Doc, Span, Token

import requests
import plac
import json
import operator

class EntityLinker(object):

    name = "abstract_entity_linker"

    def __init__(self):
        pass

    def __call__(self, doc):
        pass

class AgdistisEntityLinker(EntityLinker):

    name = 'agdistis_linker'
    OPEN_ENTITY = '<entity>'
    CLOSE_ENTITY = '</entity>'
    NOT_FOUND_URI_BASE = 'http://aksw.org/notInWiki/'
    ENDPOINTS_BY_LANGUAGE = {
        'en': 'http://akswnc9.informatik.uni-leipzig.de:8113/AGDISTIS',
        'de': 'http://akswnc9.informatik.uni-leipzig.de:8114/AGDISTIS',
        'es': 'http://akswnc9.informatik.uni-leipzig.de:8115/AGDISTIS',
        'fr': 'http://akswnc9.informatik.uni-leipzig.de:8116/AGDISTIS'
    }

    def __init__(self, lang='en',
                 param='text',
                 filter_types=False,
                 types_whitelist=['ORG', 'PERSON', 'GPE']):

        self.url = self.ENDPOINTS_BY_LANGUAGE.get(lang)
        print('INFO: Using endpoint for lang ' + lang + ' at '+ self.url)
        self.headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        self.param = param
        self.types_whitelist = types_whitelist
        self.filter_types = filter_types

        Span.set_extension('has_dbpedia_uri', default=False)
        Span.set_extension('dbpedia_uri')

    def __call__(self, doc):
        query_text = ''.join(self._get_query_text(doc))

        print('INFO: Sending text annotated by spaCy NER component ' + query_text)
        dbpedia_entities = self._get_annotations_from_service(query_text)

        self._add_dbpedia_uris(doc, dbpedia_entities)

        return doc

    def _get_annotations_from_service(self, text):
        response = requests.post(self.url, data=self._get_query_param(text), headers=self.headers)
        dbpedia_entities = response.json()
        dbpedia_entities.sort(key=lambda e: e.get('start'))
        return dbpedia_entities

    def _add_dbpedia_uris(self, doc, dbpedia_entities):
        counter_ents = 0
        for i, ent in enumerate(doc.ents):
            if(self._is_allowed_type(ent.label_)):
                dbpedia_url = dbpedia_entities[counter_ents].get('disambiguatedURL')
                if(self._is_disambiguated(dbpedia_url)):
                    ent._.set('dbpedia_uri', dbpedia_url)
                    ent._.set('has_dbpedia_uri', True)
                counter_ents += 1

    def _get_query_text(self, doc):
        flatten = lambda l: [item for sublist in l for item in sublist]
        return flatten([self._get_text_annotations_from_token(tok, len(doc)) for tok in doc])

    def _is_inside_entity(self, token):
        return token.ent_iob_ != 'O' and token.ent_iob_ != 'B'

    def _is_allowed_type(self, type_label):
        return (not self.filter_types) or (type_label in self.types_whitelist)

    def _is_disambiguated(self, url):
        return not url.startswith(self.NOT_FOUND_URI_BASE)

    def _is_in_doc_offset(self, i, doc_len):
        return i < doc_len

    def _get_text_annotations_from_token(self, tok, doc_len):
        text = []
        if(tok.ent_iob_ == 'B' and self._is_allowed_type(tok.ent_type_)):
            text.append(self.OPEN_ENTITY)
            text.append(tok.orth_)
            i = 1
            while(self._is_in_doc_offset(tok.i + 1, doc_len) and self._is_inside_entity(tok.nbor(i))):
                if(i == 1):
                    text.append(tok.whitespace_)
                text.append(tok.nbor(i).orth_)
                if(self._is_in_doc_offset(tok.i + 2, doc_len) and self._is_inside_entity(tok.nbor(i+1))):
                    text.append(tok.nbor(i).whitespace_)
                i += 1
            text.append(self.CLOSE_ENTITY)
            text.append(tok.whitespace_)
        if(tok.ent_iob_ == 'O'):
            text.append(tok.text_with_ws)
        return text

    def _get_query_param(self, text):
        query = {self.param: text}
        return query
