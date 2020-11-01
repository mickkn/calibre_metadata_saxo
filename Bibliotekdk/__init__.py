#!/usr/bin/env python
from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL v3'
__copyright__ = '2020, Mick Kirkegaard (mickkn@gmail.com)'
__docformat__ = 'restructuredtext el'

import socket
import time
import datetime
import json
try:
    from queue import Empty, Queue
except ImportError:
    from Queue import Empty, Queue
from six import text_type as unicode
from html5_parser import parse
from lxml.html import tostring
from threading import Thread
from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata
from calibre.library.comments import sanitize_comments_html

class Saxo(Source):
    name = 'Saxo'
    description = _('Downloads Metadata and covers from Saxo.dk')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Mick Kirkegaard'
    version = (1, 0, 0)
    minimum_calibre_version = (5, 0, 1)

    capabilities = frozenset(['identify'])
    touched_fields = frozenset(['identifier:isbn', 'title', 'authors', 'rating', 'comments', 'publisher', 'language', 'pubdate'])

    supports_gzip_transfer_encoding = True

    BASE_URL = 'https://www.saxo.com/dk/products/search?query='

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        
        # Print outs
        print("Identify")
        print("    Identifiers are: ", identifiers)

        # Create matches list
        matches = []

        # Initialize browser object
        br = self.browser
        
        # Get ISBN number and report
        isbn = identifiers.get('isbn', None)
        if isbn:
            print("    Found isbn %s" % (isbn))
            matches.append('%s%s' % (Saxo.BASE_URL, isbn))
        # Return if no ISBN
        if abort.is_set():
            return

        # Report the matches
        log.info("    Matches are: ", matches)

        # Setup worker thread
        workers = [Worker(url, result_queue, br, log, i, self) for i, url in enumerate(matches)]

        # Start working
        for w in workers:
            w.start()
            # Delay a little for every worker
            time.sleep(0.1)

        while not abort.is_set():
            a_worker_is_alive = False
            for w in workers:
                w.join(0.2)
                if abort.is_set():
                    break
                if w.is_alive():
                    a_worker_is_alive = True
            if not a_worker_is_alive:
                break

        return None

def parse_comments(root):
    # Look for description
    description_node = root.xpath('(//div[@class="product-page-block"]//p)[1]')
    if description_node:
        desc = description_node[0] if len(description_node) == 1 else description_node[1]
        less_link = desc.xpath('a[@class="actionLinkLite"]')
        if less_link is not None and len(less_link):
            desc.remove(less_link[0])
        comments = tostring(desc, method='html', encoding=unicode).strip()
        while comments.find('  ') >= 0:
            comments = comments.replace('  ', ' ')
        if "Fil størrelse:" in comments:
            comments = comments.replace(comments.split(".")[-1], "</p>")
        comments = sanitize_comments_html(comments)
        return comments

class Worker(Thread):  # Get details
    '''
    Get book details from Saxos book page in a separate thread
    '''
    def __init__(self, url, result_queue, browser, log, relevance, plugin, timeout=20):
        Thread.__init__(self)
        self.title = None
        self.isbn = None
        self.daemon = True
        self.url = url
        self.result_queue = result_queue
        self.log = log
        self.language = None
        self.timeout = timeout
        self.relevance = relevance
        self.plugin = plugin
        self.browser = browser.clone_browser()
        self.cover_url = None
        self.authors = []
        self.comments = None
        self.pubdate = None

        lm = {
            'eng': ('English', 'Engelsk'),
            'dan': ('Danish', 'Dansk'),
        }
        self.lang_map = {}
        for code, names in lm.items():
            for name in names:
                self.lang_map[name] = code

    def run(self):
        self.log.info("    Worker.run: self: ", self)
        try:
            self.get_details()
        except:
            self.log.exception('get_details failed for url: %r' % self.url)

    def get_details(self):
        self.log.info("    Worker.get_details:")
        self.log.info("        self:     ", self)
        self.log.info("        self.url: ", self.url)

        # Get some data from the website
        try:
            raw = self.browser.open_novisit(self.url, timeout=self.timeout).read().strip()
        # Do some error handling if it fails to read data
        except Exception as e:
            if callable(getattr(e, 'getcode', None)) and e.getcode() == 404:
                self.log.error('URL malformed: %r' % self.url)
                return
            attr = getattr(e, 'args', [None])
            attr = attr if attr else [None]
            if isinstance(attr[0], socket.timeout):
                msg = 'Bookmeta for saxo timed out. Try again later.'
                self.log.error(msg)
            else:
                msg = 'Failed to make details query: %r' % self.url
                self.log.exception(msg)
            return

        # Do some error handling
        if "<title>404 - " == raw:
            self.log.error('URL malformed: %r' % self.url)
            return

        # Clean the html data
        try:
            root = parse(raw)
        except:
            self.log.error("Error cleaning HTML")
            return

        # Get the json data
        try:
            json_raw = root.xpath('(//script[@type="application/ld+json"])[2]')
            json_root = json.loads(json_raw[0].text.strip())
            #print(json.dumps(json_root, indent=4, sort_keys=True))
        except:
            self.log.error("Error loading JSON data")
            return

        # Strip the title of the book
        try:
            self.title = json_root['name']
        except:
            self.log.exception('Error parsing title for url: %r' % self.url)

        # Strip the author of the book here
        try:
            author_node = root.xpath('//h2[@class="product-page-heading__autor"]//a')
            for name in author_node:
                self.authors.append(name.text.strip())
        except:
            self.log.exception('Error parsing authors for url: %r' % self.url)
            self.authors = None

        # Strip the rating
        try:
            self.rating = float(json_root['aggregateRating']['ratingValue'])
        except:
            self.log.exception('Error parsing rating for url: %r' % self.url)
            self.rating = 0.0

        # Strip the ISBN of the book
        try:
            self.isbn = json_root['isbn']
        except:
            self.log.exception('Error parsing isbn for url: %r' % self.url)
            self.isbn = None

        # Strip the comments/blurb of the book
        try:
            self.comments = parse_comments(root)
        except:
            self.log.exception('Error parsing comments for url: %r' % self.url)
            self.comments = None

        # Strip the URL for cover here
        try:
            self.cover_url = json_root['image']
            self.log.info('Parsed URL for cover:%r' % self.cover_url)
            self.plugin.cache_identifier_to_cover_url(None, self.cover_url)
        except:
            self.log.exception('Error parsing cover for url: %r' % self.url)
            self.has_cover = bool(self.cover_url)

        # Strip the book Publisher here
        try:
            self.publisher = json_root['publisher']['name']
        except:
            self.log.exception('Error parsing publisher for url: %r' % self.url)

        # Strip the language of the book
        try:
            language = json_root['inLanguage']['name']
            language = self.lang_map.get(language, None)
            self.language = language
        except:
            self.log.exception('Error parsing language for url: %r' % self.url)

        # Strip the date of publish here
        try:
            pubdate_node = root.xpath('(//dl[@class="product-info-list"]//dd)[2]') # Format dd-mm-yyyy
            date_str = pubdate_node[0].text.strip()
            format_str = '%d-%m-%Y' # The format
            self.pubdate = datetime.datetime.strptime(date_str, format_str)
        except:
            self.log.exception('Error parsing published date for url: %r' % self.url)

        # Setup the metadata
        meta_data = Metadata(self.title, self.authors)
        meta_data.set_identifier('isbn', self.isbn)

        # Set rating
        if self.rating:
            try:
                meta_data.rating = self.rating
            except:
                self.log.exception('Error loading rating')
        # Set ISBN
        if self.isbn:
            try:
                meta_data.isbn = self.isbn
            except:
                self.log.exception('Error loading ISBN')
        # Set relevance
        if self.relevance:
            try:
                meta_data.source_relevance = self.relevance
            except:
                self.log.exception('Error loading relevance')
        # Set cover url
        if self.cover_url:
            try:
                meta_data.cover_url = self.cover_url
            except:
                self.log.exception('Error loading cover_url')
        # Set publisher
        if self.publisher:
            try:
                meta_data.publisher = self.publisher
            except:
                self.log.exception('Error loading publisher')
        # Set language
        if self.language:
            try:
                meta_data.language = self.language
            except:
                self.log.exception('Error loading language')
        # Set comments/blurb
        if self.comments:
            try:
                meta_data.comments = self.comments
            except:
                self.log.exception("Error loading comments")
        # Set publisher data
        if self.pubdate:
            try:
                meta_data.pubdate = self.pubdate
            except:
                self.log.exception('Error loading pubdate')

        # Put meta data
        self.plugin.clean_downloaded_metadata(meta_data)
        self.result_queue.put(meta_data)

if __name__ == '__main__':  # tests
    # To run these test use:
    # calibre-customize -b . ; calibre-debug -e __init__.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin, title_test, authors_test)

    tests = [(  # A book with an ISBN
                {
                'identifiers': {'isbn': '9788702015379'},
                'title': 'Eventyret om ringen', 
                'authors': ['J. R. R. Tolkien']
                },[
                    title_test('Eventyret om ringen', exact=True),
                    authors_test(['J. R. R. Tolkien'])]
            ), 
            (   # A book with two Authors
                {
                'identifiers': {'isbn': '9788740065756'},
                'title': 'Casper', 
                'authors': ['Martin Kongstad']
                },[
                    title_test('Casper', exact=True),
                    authors_test(['Martin Kongstad'])]
            )
            ]

    test_identify_plugin(Saxo.name, tests)
