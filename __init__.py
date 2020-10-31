#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL v3'
__copyright__ = '2020, Mick Kirkegaard (mickkn@gmail.com)'
__docformat__ = 'restructuredtext el'

import socket
import datetime
from threading import Thread
from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata


class Saxo(Source):
    name = 'Saxo'
    description = _('Downloads Metadata and covers from Saxo.dk')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Mick Kirkegaard'
    version = (1, 0, 0)
    minimum_calibre_version = (0, 8, 4)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['identifier:isbn', 'title', 'authors', 'tags', 'publisher', 'pubdate', 'series'])

    supports_gzip_transfer_encoding = True

    BASE_URL = 'http://metablogging.gr/bookmeta/index.php?isbn='

    def get_book_url(self, identifiers):
        return

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        return

    def get_cached_cover_url(self, identifiers):
        return

    def cached_identifier_to_cover_url(self, id_):
        return

    def _get_cached_identifier_to_cover_url(self, id_):
        return

    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        return


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
            self.log.info("Fetch some data from the website here")
        except:
            return

        # Do some error handling
        #if '<title>404 - ' in raw:
        #    self.log.error('URL malformed: %r' % self.url)
        #    return

        # Clean the html data
        try:
            self.log.info("Clean the html data here")
        except:
            return

        # Strip the title of the book
        try:
            #self.title = root['title'].strip()
            self.title = "Test title"
            self.log.info("Strip the book title here")
        except:
            self.log.exception('Error parsing title for url: %r' % self.url)

        # Strip the aithor of the book here
        try:
            #self.authors = [root['authors'].strip()]
            #self.log.info(self.authors)
            self.authors = "Test Author"
            self.log.info("Strip the book authors here")
        except:
            self.log.exception('Error parsing authors for url: %r' % self.url)
            self.authors = None

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
            self.pubdate = "Test publisher data"
            self.log.info("Strip the year of publish here")
        except:
            self.log.exception('Error parsing published date for url: %r' % self.url)

        # Setup the metadata
        meta_data = Metadata(self.title, self.authors)
        meta_data.set_identifier('isbn', self.isbn)

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
        if self.pubdate:
            try:
                if self.pubdate not in (self.yr_msg1, self.yr_msg2):
                    d = datetime.date(int(self.pubdate), 1, 1)
                    meta_data.pubdate = d
            except:
                self.log.exception('Error loading pubdate')

        self.plugin.clean_downloaded_metadata(meta_data)
        self.result_queue.put(meta_data)


if __name__ == '__main__':
    # To run these test use:
    # calibre-debug -e __init__.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin, title_test, authors_test, series_test)

    test_identify_plugin(Saxo.name,
                         [
                             (  # A book with an ISBN
                                 {'identifiers': {'isbn': '9780385340588'},
                                  'title': '61 Hours', 'authors': ['Lee Child']},
                                 [title_test('61 Hours', exact=True),
                                  authors_test(['Lee Child']),
                                  series_test('Jack Reacher', 14.0)]
                             ),

                         ])
