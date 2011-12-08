import time, uuid

from scrapy.spider import BaseSpider
from scrapy.http import Request
from scrapy.contrib.linkextractors.sgml import SgmlLinkExtractor
from scrapy import log

from hcicrawler.lru import url_to_lru
from hcicrawler.items import Page
from hcicrawler.samples import MONGODB_INPUT

class PagesCrawler(BaseSpider):

    name = 'pages'

    def __init__(self, **kw):
        # TODO: use spider arguments
        super(PagesCrawler, self).__init__(**MONGODB_INPUT)
        # TODO: get from scrapyd
        self.jobid = uuid.uuid4()

    def start_requests(self):
        self.log("Starting crawl task - jobid: %s" % self.jobid)
        self.link_extractor = SgmlLinkExtractor()
        for url in self.start_urls:
            yield Request(url, callback=self.parse)

    def parse(self, response):
        lru = url_to_lru(response.url)
        depth = response.meta['depth']
        lrulinks = []
        for link in self.link_extractor.extract_links(response):
            try:
                lrulink = url_to_lru(link.url)
            except ValueError, e:
                self.log("Error converting URL to LRU: %s" % e, log.ERROR)
                continue
            lrulinks.append(lrulink)
            if self._should_follow(depth, lru, lrulink):
                yield Request(link.url, callback=self.parse)
        yield self._make_page(response, lru, lrulinks)

    def _make_page(self, response, lru, lrulinks):
        p = Page()
        p['url'] = response.url
        p['lru'] = lru
        p['status'] = response.status
        p['size'] = len(response.body)
        p['encoding'] = response.encoding
        p['body'] = response.body_as_unicode()
        p['timestamp'] = int(time.time())
        p['lrulinks'] = lrulinks
        p['depth'] = response.meta['depth']
        p['content_type'] = response.headers.get('content-type').partition(';')[0]
        return p

    def _should_follow(self, depth, lru, lrulink):
        return depth < self.maxdepth \
            and not any((lru.startswith(p) for p in self.discover_prefixes)) \
            and any((lrulink.startswith(p) for p in self.follow_prefixes)) \
            and not any((lrulink.startswith(p) for p in self.discover_prefixes))