#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL v3'
__copyright__ = '2020, Mick Kirkegaard (mickkn@gmail.com)'
__docformat__ = 'restructuredtext el'

import socket
import time
import datetime

from six import text_type as unicode
from html5_parser import parse
from lxml.html import fromstring, tostring
from threading import Thread
from calibre.ebooks import normalize
from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata
from calibre.library.comments import sanitize_comments_html

class Saxo(Source):
    name = 'Saxo'
    description = _('Downloads Metadata and covers from Saxo.dk')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Mick Kirkegaard'
    version = (1, 0, 0)
    minimum_calibre_version = (0, 8, 4)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['identifier:isbn', 'title', 'authors', 'tags', 'comments', 'publisher', 'pubdate', 'series'])

    supports_gzip_transfer_encoding = True

    BASE_URL = 'https://www.saxo.com/dk/products/search?query='

    def get_book_url(self, identifiers):
        return

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        
        # Print outs
        print("identify")
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

    def get_cached_cover_url(self, identifiers):
        return

    def cached_identifier_to_cover_url(self, id_):
        return

    def _get_cached_identifier_to_cover_url(self, id_):
        return

    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        return


def parse_comments(root):
    # Look for description
    description_node = root.xpath('//div[@class="product-page-block__container product-page-block__container--more product-page-block__container--opened"]//p')
    print(description_node[0].text.strip())
    for i in description_node:
        print(i.text.strip())
    """
    if description_node:
        desc = description_node[0] if len(description_node) == 1 else description_node[1]
        less_link = desc.xpath('a[@class="actionLinkLite"]')
        if less_link is not None and len(less_link):
            desc.remove(less_link[0])
        comments = tostring(desc, method='html', encoding=unicode).strip()
        while comments.find('  ') >= 0:
            comments = comments.replace('  ', ' ')
        comments = sanitize_comments_html(comments)
        return comments
    """

class Worker(Thread):  # Get details

    '''
    Get book details from Saxos book page in a separate thread
    '''
    def __init__(self, url, result_queue, browser, log, relevance, plugin, timeout=20):
        Thread.__init__(self)
        self.title = None
        self.daemon = True
        self.url = url
        self.result_queue = result_queue
        self.log = log
        self.timeout = timeout
        self.relevance = relevance
        self.plugin = plugin
        self.browser = browser.clone_browser()
        self.cover_url = None
        self.series_index = None
        self.authors = []
        self.comments = None
        self.yr_msg1 = 'No publishing year found'
        self.yr_msg2 = 'An error occured'

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
            #self.log.info(raw)
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
            #root = json.loads(raw)
        except:
            self.log.error("Error cleaning HTML")
            return

        # Strip the title of the book
        try:
            title_node = root.xpath('//h1[@class="product-page-heading__title"]')
            if not title_node:
                return None
            self.title = title_node[0].text.strip()
            self.log.info(f"Title: {title_node[0].text.strip()}")
        except:
            self.log.exception('Error parsing title for url: %r' % self.url)

        # Strip the author of the book here
        #TODO Fix multiply authors
        try:
            author_node = root.xpath('//h2[@class="product-page-heading__autor"]//a')
            self.authors.append(author_node[0].text.strip())
            self.log.info(f"Author: {author_node[0].text.strip()}")
        except:
            self.log.exception('Error parsing authors for url: %r' % self.url)
            self.authors = None

        # Strip the tags of the book

        # Strip the comments of the book
        try:
            self.comments = parse_comments(root)
        except:
            self.log.exception('Error parsing comments for url: %r' % self.url)
            self.comments = None

        # Strip the URL for cover here
        try:
            #self.cover_url = root['cover_url']
            #self.log.info('Parsed URL for cover:%r' % self.cover_url)
            #self.plugin.cache_identifier_to_cover_url(self.biblionetid, self.cover_url)
            self.cover_url = "Test cover url"
            self.log.info("Strip cover url here")
        except:
            self.log.exception('Error parsing cover for url: %r' % self.url)
            self.has_cover = bool(self.cover_url)

        # Strip the book Publisher here
        try:
            #self.publisher = root['publisher']
            #self.log.info('Parsed publisher:%s' % self.publisher)
            self.publisher = "Test publisher"
            self.log.info("Strip the publisher name here")
        except:
            self.log.exception('Error parsing publisher for url: %r' % self.url)

        # Strip the book tags here
        try:
            #self.tags = root['categories'].replace('DDC: ', 'DDC:').replace('-', '').split()[:-1]
            #self.log.info('Parsed tags:%s' % self.tags)
            self.tags = "Test tag"
            self.log.info("Strip the book tags here")
        except:
            self.log.exception('Error parsing tags for url: %r' % self.url)

        # Strip the year of publish here
        try:
            #self.pubdate = root['yr_published']
            #self.log.info('Parsed publication date:%s' % self.pubdate)
            self.pubdate = "11-01-20"
            self.log.info("Strip the year of publish here")
        except:
            self.log.exception('Error parsing published date for url: %r' % self.url)

        # Setup the metadata
        meta_data = Metadata(self.title, self.authors)
        #meta_data.set_identifier('isbn', self.isbn)    

        if self.series_index:
            try:
                meta_data.series_index = float(self.series_index)
            except:
                self.log.exception('Error loading series')
        if self.relevance:
            try:
                meta_data.source_relevance = self.relevance
            except:
                self.log.exception('Error loading relevance')
        if self.cover_url:
            try:
                meta_data.cover_url = self.cover_url
            except:
                self.log.exception('Error loading cover_url')
        if self.publisher:
            try:
                meta_data.publisher = self.publisher
            except:
                self.log.exception('Error loading publisher')
        if self.tags:
            try:
                meta_data.tags = self.tags
            except:
                self.log.exception('Error loading tags')
        if self.comments:
            try:
                meta_data.comments = self.comments
            except:
                self.log.exception("Error loading comments")
        if self.pubdate:
            try:
                if self.pubdate not in (self.yr_msg1, self.yr_msg2):
                    d = datetime.date(int(self.pubdate), 1, 1)
                    meta_data.pubdate = d
            except:
                self.log.exception('Error loading pubdate')

        self.plugin.clean_downloaded_metadata(meta_data)
        self.result_queue.put(meta_data)

if __name__ == '__main__':  # tests
    # To run these test use:
    # calibre-customize -b . ; calibre-debug -e __init__.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin, title_test, authors_test, series_test)

    tests = [(  # A book with an ISBN
                {
                'identifiers': {'isbn': '9788740065756'},
                'title': 'Casper', 
                'authors': ['Martin Kongstad']
                },[
                    title_test('Casper', exact=True),
                    authors_test(['Martin Kongstad'])]
            ), 
            (   # A book with two Authors
                {
                'identifiers': {'isbn': '9781405188289'},
                'title': 'Hollywood Film 1963-1976', 
                'authors': ['Drew Casper', 'Casper']
                },[
                    title_test('Hollywood Film 1963-1976', exact=True),
                    authors_test(['Drew Casper', 'Casper'])]
            )
            ]

    test_identify_plugin(Saxo.name, tests)
