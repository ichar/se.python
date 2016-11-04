# -*- coding: utf-8 -*-

import os
import sys
import time
import random
import datetime
import traceback
import re

from collections import OrderedDict
from operator import itemgetter

if sys.version_info[0] > 2:
    from bs4 import BeautifulSoup, Tag, NavigableString, Comment
    from http.cookiejar import LWPCookieJar
    from urllib.request import Request, urlopen
    from urllib.parse import quote_plus, urlparse, parse_qs, unquote
    from urllib.error import HTTPError
else:
    from BeautifulSoup import BeautifulSoup, Tag, NavigableString, Comment
    from cookielib import LWPCookieJar
    from urllib import quote_plus, unquote
    from urllib2 import Request, urlopen, HTTPError
    from urlparse import urlparse, parse_qs

import requests

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException

from config import (
     Config, ERRORLOG as errorlog, basedir, IsDebug, IsDeepDebug, IsTrace,
     SEARCH_ENGINES, SEARCH_MODES, SEARCH_OPTIONS,
     USER_AGENTS, ADDRESS_KEYS, MANAGER_KEYS, UNUSED_TAGS, TAG_RATING)

from .logger import Logger, log, print_exception, conv_rus_eng, EOR, EOL
from .utils import (
     capitalize, mkdir, is_num, sclean,
     get_domain, get_email_domain, get_emails, get_phones, get_address, get_manager, get_fio,
     is_key_inside, is_value_inside, is_valid_alias, is_valid_href, is_valid_info, 
     is_valid_email, is_valid_phone, is_valid_address, is_valid_manager, is_valid_fio,
     xsplit, usplitter, spent_time, make_cookiejar_from_dict, make_html
     )

_global_html_nesting_limit = Config['GLOBAL'].getint('html_nesting_limit') or 999
_global_html_tags_limit = Config['GLOBAL'].getint('html_tags_limit') or 999
_global_high_weight_domain = Config['GLOBAL'].getint('high_weight_domain') or 20
_global_spended_time_limit = Config['GLOBAL'].getint('spended_time_limit') or 30


def _out(s):
    try:
        return unicode(s)
    except:
        return s

def _random_user_agent(forced=None):
    return forced is None and Config['GLOBAL'].getboolean('cookies_random') and \
        random.choice(USER_AGENTS) or \
        USER_AGENTS[forced]

def _get_home():
    return os.getenv('HOME') or os.getenv('USERHOME') or \
        Config['GLOBAL'].get('cookies_folder', './cookies')

def _get_page_agent():
    x = Config['GLOBAL'].getint('page_agent')
    return x > -1 and USER_AGENTS[x] or random.choice(USER_AGENTS)

get_page_agent = _get_page_agent

def _check_consisted_url(query, value):
    m = []
    for a in [x.split('.') for x in get_domain(value).split('/') if x]:
        m += a
    for x in [re.sub(r'[\-\_]', ' ', x) for x in m]:
        if x and x not in m:
            m.append(x)
    return query in m or conv_rus_eng(query) in m

def _check_consisted_title(query, value, form=None):
    v = value.lower()
    return ''.join([x in v and '1' or '' for x in xsplit(query, ' -\'')]) and (not form or form in v) and True or False

def _check_consisted_email(query, value):
    return query in value or conv_rus_eng(query) in value

##  -----------------------
##  Public Helper Functions
##  -----------------------

def parser_get_alias(url):
    x = list(filter(lambda x: not (not x or x.startswith('?')), 
        re.sub(r'[*?\s\\]', '_', 
        re.sub(r'[\'"+&=]', '', 
        unquote(url)
    )).split('/')))[-1]
    return x[:100]

def parser_check_attrs(attrs, tag):
    try:
        t_attrs = tag.attrs
    except:
        t_attrs = None
    if not t_attrs:
        return False
    for k in attrs:
        if attrs[k] in t_attrs[k].lower().split():
            return True
    return False

def parser_add_href(domain, url, level=0, callback=None):
    if not (url and domain):
        return
    ps = url.split('&')
    while len(ps):
        x = ps.pop(0)
        if x and (x in ps or x.startswith('javascript') or x in '/?&'):
            return

    href = domain != url and re.sub(r'([^:])//', r'\1/', ( \
        url.startswith(domain) and url or 
        url.startswith('http') and url or 
        '%s%s' % (domain, url)
    ).strip())

    if not is_valid_href(href):
        return
    if url in domain:
        return

    if callback is None:
        return href

    callback(level, href)

def parser_sibling(tag, dir='forward'):
    t = tag
    v = ''
    
    def _get_sibling_content(tag):
        return ' '.join([x.string.strip() for x in tag.children if isinstance(x, NavigableString)])

    while not (t is None or v):
        if dir == 'forward':
            t = t.next_sibling
        else:
            t = t.previous_sibling
        if t is None:
            break
        if isinstance(t, NavigableString):
            v = t.string
        elif isinstance(t, Tag) and t.name not in UNUSED_TAGS and len(t.contents):
            v = _get_sibling_content(t)
        v = re.sub(r'\n', '', v or '')

    return v or ''

def parser_unquote(value):
    return value and unquote(value) or ''

########################################################

##  =====================
##  HTTP Request Scrapers
##  =====================

class MyWebDriver(webdriver.Chrome):

    def __init__(self, **kw):
        self.w3c = True
        super(MyWebDriver, self).__init__(**kw)

    def start_client(self):
        self.command_executor._commands.update({ \

            'MINIMIZE_WINDOW' : ('POST', '/session/$sessionId/window/$windowHandle/minimize'),
            'W3C_MINIMIZE_WINDOW' : ('POST', '/session/$sessionId/window/minimize')

        })

    def minimize_window(self):
        self.execute(self.w3c and 'W3C_MINIMIZE_WINDOW' or 'MINIMIZE_WINDOW', {"windowHandle": "current"})


class Cookies:
    _mask = '.%s-cookie'
    
    def __init__(self, name):
        self.name = self._mask % name
        self._cookies = LWPCookieJar(os.path.join(_get_home(), self.name))

    def get(self):
        return self._cookies

    def set(self, cookies):
        self._cookies = cookies

    def load(self):
        try:
            self._cookies.load()
        except Exception:
            pass

    def make_cookies(self, values):
        make_cookiejar_from_dict(values, self._cookies)
        self.save()

    def add_header(self, request):
        self._cookies.add_cookie_header(request)

    def extract(self, response, request):
        self._cookies.extract_cookies(response, request)

    def save(self):
        self._cookies.save()


class BaseRequest(object):
    
    def __init__(self, alias, url, timeout=None):
        self.alias = alias
        self.url = url
        self.timeout = timeout
        
        self._cookies = None
        self._headers = None
        self._driver = None
        self._error = None

    def _init_state(self, logger=None):
        self.logger = logger
        self._get_cookies()

    def _get_cookies(self):
        self._cookies = Cookies(self.alias)
        self._cookies.load()

    def is_valid_content_type(self, response):
        content_type = response.headers.get('Content-Type')
        return 'text/html' in content_type

    def _set_cookies(self, response, request):
        self._cookies.extract(response, request)
        self._cookies.save()

    def _http(self, agent=None, timeout=None, **kw):
        request = Request(self.url)

        html = ''

        if agent:
            request.add_header('User-Agent', agent)

        self._cookies.add_header(request)

        if self._headers:
            for key in self._headers:
                request.add_header(key, self._headers[key])

        try:
            response = urlopen(request, timeout=timeout or self.timeout)
        except Exception:
            self._error = True
            raise

        self._cookies.extract(response, request)

        if self.is_valid_content_type(response):
            html = response.read()

        response.close()
        self._cookies.save()

        return response, html

    def _requests(self, agent=None, timeout=None, **kw):
        if kw.get('use_cookies'):
            response = requests.get(self.url, 
                json=kw.get('data'), headers=kw.get('headers'), cookies=self._cookies.get())
        else:
            response = requests.get(self.url)
            self._cookies.set(response.cookies)

        return response, response.text

    def _selenium(self, agent=None, timeout=None, **kw):
        if not Config['SELENIUM'].getboolean('enabled'):
            return None

        html = ''

        pause = kw.get('pause') or Config['SELENIUM'].getfloat('pause')
        if pause > 0:
            time.sleep(pause)

        try:
            #self._driver = MyWebDriver() #service_log_path=Config['SELENIUM'].get('log')
            self._driver = webdriver.PhantomJS()
        except WebDriverException as e:
            raise

        #self._driver.minimize_window()
        #self._driver.set_window_size(0, 0)
        #self._driver.set_window_position(2000, 2000)
        self._driver.set_page_load_timeout(timeout or self.timeout)

        self._driver.get(self.url)

        if kw.get('use_cookies'):
            self._cookies.make_cookies(self._driver.get_cookies())

        if kw.get('inner_html'):
            try:
                html = self._driver.execute_script('return document.body.innerHTML;')
            except WebDriverException as e:
                pass

        if not html:
            html = self._driver.page_source

        return html

    def open(self, url, agent=None, **kw):
        if url:
            self.url = url
        
        response = None
        self._error = False
        html = ''

        try:
            if kw.get('selenium') or ( \
                Config['SELENIUM'].getboolean('auto') and self._rating > Config['SELENIUM'].getint('rating')):
                    html = self._selenium(**kw)
        except:
            self._error = True
            print_exception()
        if not html:
            if kw.get('use_requests'):
                response, html = self._requests(**kw)
            else:
                response, html = self._http(agent=agent, **kw)

        return response, html

    def close(self):
        if self._driver is not None:
            self._driver.quit()


class AbstructSearchEngine(BaseRequest):

    def __init__(self, alias, urls, timeout, **kw):
        BaseRequest.__init__(self, alias, None, \
            timeout=timeout or Config['DEFAULT'].getfloat('default_timeout')
        )

        self.urls = urls

        self._parser = kw.get('parser') or Config['DEFAULT'].get('default_html_parser')
        self._search_tags = dict([tuple(tag.strip().split(':')) for tag in kw.get('tags', '').split(',')])
        self._search_parent = kw.get('parent') or ''
        self._search_nav = kw.get('nav') or ''

        self._trace = IsTrace and kw.get('trace') and True or False

        self._use_selenium = kw.get('selenium') and True or False
        self._headers = kw.get('headers') or {}

        self._soup = None

    def _init_state(self, logger=None):
        super()._init_state(logger)

        if self.logger is None:
            self._trace = False

        if self._trace:
            self.logger.out('%s' % self.alias)

    def get_page(self, url, forced=None):
        pass

    def filter_result(self, link):
        pass

    def find_anchors(self):
        pass

    def search(self, query, **kw):
        pass


class BaseSearchEngine(AbstructSearchEngine):
    
    def __init__(self, alias, urls, timeout=2.0, **kw):
        AbstructSearchEngine.__init__(self, alias, urls, timeout, **kw)

    def _init_state(self, logger=None):
        super()._init_state(logger)

    def get_page(self, url, forced=None):
        """
            Request the given URL and return the response page
        """
        try:
            response, html = self.open(url, _random_user_agent(forced), selenium=self._use_selenium)
        except:
            self.close()
            raise

        self.close()

        if not html:
            raise RuntimeError("No html received")

        return html

    def filter_result(self, link):
        """
            Filter links found in the SE result pages HTML code.
            Returns None if the link doesn't yield a valid result.
        """
        try:
            # Valid results are absolute URLs not pointing to a SE domain
            # like images.google.com or googleusercontent.com
            o = urlparse(link, 'http')
            if o.netloc and self.alias not in o.netloc:
                return link

            # Decode hidden URLs.
            if link.startswith('/url?'):
                link = parse_qs(o.query)['q'][0]

                # Valid results are absolute URLs not pointing to a SE domain
                # like images.bing.com or googleusercontent.com
                o = urlparse(link, 'http')
                if o.netloc and self.alias not in o.netloc:
                    return link

        # Otherwise, or on error, return None.
        except Exception:
            pass
        return None

    def find_anchors(self):
        s = None
        value = None

        def is_valid_anchors_attr(v):
            return v and value in v.split() and True or False

        for key in self._search_tags:
            if s is not None:
                self._soup = s
                break
            value = self._search_tags[key]
            if not value:
                continue
            if key == 'class':
                s = self._soup.find(class_=is_valid_anchors_attr)
            if key == 'id':
                s = self._soup.find(id=value)

        return self._soup.findAll('a')

    def search(self, query, tld='com', lang='en', num=10, start=0, stop=None, pause=2.0,
               only_standard=False, parser=None, trace=False):
        """
            Search the given query string using given search engine.
        """
        if not num or num < 0:
            num = 10
        if not start or start < 0:
            start = 0
        if not stop or stop < 0:
            stop = num + start

        if self.logger is None:
            trace = False

        # Set of hashes for the results found.
        # This is used to avoid repeated results.
        hashes = set()

        if IsDeepDebug and self.logger is not None:
            self.logger.out('query[%s]' % query)

        # Prepare the search string.
        query = quote_plus(query)
        url = self.urls.get('home') % vars()

        if trace:
            self.logger.out(url)

        # Grab the cookie from the home page.
        self.get_page(url)
    
        # Prepare the URL of the first request.
        if start:
            page = int(start/num) + 1
            if num % 10 == 0:
                url = self.urls.get('next_page') % vars()
            else:
                url = self.urls.get('next_page_num') % vars()
        else:
            page = 1
            if num % 10 == 0:
                url = self.urls.get('search') % vars()
            else:
                url = self.urls.get('search_num') % vars()
    
        # Loop until we reach the maximum result, if any (otherwise, loop forever).
        while not stop or start < stop:
            self._soup = None

            # Sleep between requests.
            time.sleep(pause)

            if trace:
                self.logger.out('%s:%s' % (start, url))

            # Request the Bing Search results page.
            html = self.get_page(url)

            if trace:
                self.logger.out('html:%s' % len(html))

            # Parse the response and process every anchored URL.
            self._soup = BeautifulSoup(html, parser or self._parser)

            if trace:
                self.logger.out('soup:%s' % (self._soup and len(self._soup)))

            anchors = self.find_anchors()

            if trace:
                self.logger.out('a:%s' % len(anchors))

            for a in anchors:
                # Get the URL from the anchor tag.
                try:
                    link = a['href']
                except KeyError:
                    continue

                # Filter invalid links and links pointing to SE itself.
                link = self.filter_result(link)
                if not link:
                    continue

                if not is_valid_href(link):
                    continue

                # Leave only the "standard" results if requested.
                # Otherwise grab all possible links.
                if trace:
                    self.logger.out('parent:%s' % (a.parent and a.parent.name.lower()))

                if only_standard and not ( \
                        self._search_parent and 
                        a.parent and 
                        a.parent.name.lower() == self._search_parent
                    ):
                    continue

                if trace:
                    self.logger.out('%s' % link)

                # Discard repeated results.
                h = hash(link)
                if h in hashes:
                    continue
                hashes.add(h)

                # Yield the result.
                yield link

            # End if there are no more results.
            if self._search_nav and not self._soup.find(id=self._search_nav):
                break

            # Prepare the URL for the next request.
            start += num
            page = int(start/num) + 1
            if num % 10 == 0:
                url = self.urls.get('next_page') % vars()
            else:
                url = self.urls.get('next_page_num') % vars()

        #self.close()


class Page(BaseRequest):

    def __init__(self, alias, query, url, level, num, callback, keywords, so, depth, **kw):
        BaseRequest.__init__(self, alias, url, \
            timeout=kw.get('timeout') or Config['DEFAULT'].getfloat('default_timeout')
        )

        self.query = query.lower()          # Company name (main query)
        self.level = level                  # Depth of link
        self.num = num                      # Number of page
        self.callback = callback            # Main callback
        self.keywords = {}                  # Keywords: company organization form, address, another keys (contact)
        self.form = ''                      # Company organization form
        self.so = so                        # Output pointer
        self.depth = depth                  # Max link depth

        _global_optional_rating = Config['GLOBAL'].getint('optional_rating')

        if _global_optional_rating and keywords:
            s = '!'
            # Company organization form
            self.form = re.sub(r'[%s]+' % s, '', keywords[0].lower())
            # Address
            for word in keywords:
                if not s in word:
                    continue
                rating = 0
                for x in word.split(s):
                    if not x:
                        rating += _global_optional_rating
                    else:
                        x = re.sub(r'\+', '', x.lower())
                        self.keywords[x] = [0, rating, conv_rus_eng(x)]
                        break

        self._domain = get_domain(url)

        self._links = []
        self._emails = []
        self._phones = []
        self._addresses = []
        self._managers = []

        self._debug = IsDebug and kw.get('debug') and True or False
        self._trace = IsTrace and kw.get('trace') and True or False

        if 'pause' in kw:
            self.use_pause = True
            self._pause = kw.get('pause') or Config['DEFAULT'].getfloat('default_pause')
        else:
            self.use_pause = False
            self._pause = 0

        self.mode_email = kw.get('email') and True or False
        self.mode_phone = kw.get('phone') and True or False
        self.mode_address = kw.get('address') and True or False
        self.mode_manager = kw.get('manager') and True or False
        self.mode_string = kw.get('string') and True or False
        self.mode_unique = kw.get('unique') and True or False
        self.mode_top = kw.get('top') and True or False

        self._main_domain = None
        self._rating = 0

        # Valid consisted title in the body (address or manager)
        self._body_top = False
        # Search fio mode activated
        self._fio = False

        if _check_consisted_url(self.query, self.url):
            self._main_domain = self._domain
            self._rating = TAG_RATING['url']

        # Valid consisted title in the url/head (company name)
        self._top = self._rating and 1 or 0

        self._threshold = kw.get('threshold') or Config['DEFAULT'].getint('default_threshold')
        self._soup = None

        self._html_size = None
        self._html_time = None

        if self._debug:
            self.dump(self.url)
            self.dump('*'*3)

    def _init_state(self, logger=None):
        super()._init_state(logger)

        if self.logger is None:
            self._debug = False

        if self._debug:
            self.logger.out('page[%s]' % (self.url))

        self._check_rating_of_keywords(self.url, rating=TAG_RATING['url'])

    def dump(self, s, indent=0):
        if self.so is not None:
            self.so.out('%s%s' % (' '*indent, s))

    def _check_rating_of_keywords(self, value, rating=None, check=False):
        for w in self.keywords:
            d, r, e = self.keywords[w]
            if not (check and d) and (w in value or e in value):
                self._rating += (rating or r or TAG_RATING['default'])
                self.keywords[w][0] += 1

    def isError(self):
        return self._error

    def getUrlInfo(self):
        return [ \
            self.url, 
            self._html_size or 0, 
            self._html_time is not None and self._html_time.seconds or 0, 
            0,
            self._rating or 0,
        ]

    def getMainDomain(self):
        x = self._main_domain and urlparse(self._main_domain) or None
        return x and x.netloc

    def __call__(self, output, **kw):
        self._output = output
        html = ''

        #self._trace = kw.get('trace') and True or False

        if self.logger is None:
            self._debug = False
            self._trace = False

        try:
            response, html = self.open(None, _get_page_agent(), **kw)
        except KeyboardInterrupt as err:
            raise
        except:
            self.close()
            return self._output
    
        self._html_size = len(html)
        start = datetime.datetime.now()
    
        if self._debug:
            self.logger.out('html[%s]' % self._html_size)

        self._soup = BeautifulSoup(html, Config['DEFAULT'].get('default_html_parser'))

        self.title()
        self.meta()

        is_rating_valid = (not self.mode_top or self._top) and True or False

        if is_rating_valid:
            self.body()

        if self.mode_top:
            is_rating_valid = False

        if self._top:
            if len([1 for d, r, e in self.keywords.values() if not d]) == 0:
                if Config['SELENIUM'].getboolean('enabled'):
                    self._rating = Config['SELENIUM'].getint('rating') + 1
                is_rating_valid = True

        finish = datetime.datetime.now()
        self._html_time = finish - start

        if self._debug:
            self.logger.out('time[%s]' % spent_time(start, finish))
            self.logger.out('rating[%s]' % self._rating)

        if is_rating_valid and self._rating >= self._threshold and ( \
            self._top or self._body_top or Config['DEFAULT'].getboolean('default_output_valid')):

            level = self.level + 1

            if not self.depth or self.depth >= level:
                for href in self._links:
                    parser_add_href(self._domain, href, level, self.callback)
                if self._soup.body is not None:
                    for a in self._soup.body.findAll('a'):
                        href = a.attrs.get('href')
                        parser_add_href(self._domain, href, level, self.callback)

            if len(self._emails):
                if self.mode_unique:
                    self._emails = usplitter(self._emails, '?,')
                self._output.append(('email', self.url, self.alias, self.level, self._rating, self._emails))
            if len(self._phones):
                if self.mode_unique:
                    self._phones = list(set([x for x in self._phones]))
                self._output.append(('phone', self.url, self.alias, self.level, self._rating, self._phones))
            if len(self._addresses):
                self._output.append(('address', self.url, self.alias, self.level, self._rating, self._addresses))
            if len(self._managers):
                self._output.append(('manager', self.url, self.alias, self.level, self._rating, self._managers))

        self.close()

        if self._trace:
            self.logger.out('%03d:%s:%s' % (self.num, self.level, len(self._output)), without_decoration=True)

        if self._debug:
            self.dump(EOL)
            self.dump('*'*3)
            self.dump('rating:%s, threshold:%s, top:%s, body_top:%s' % (self._rating, self._threshold, self._top, self._body_top))

        return self._output

    def _content(self, name):
        items = self._soup.findAll(name)

        if self._debug:
            self.logger.out('meta[%s]' % len(items))
            self.dump('%s[%s]:' % (name, len(items)))

        return items

    def _get_tag_attrs(self, tag):
        return tag.attrs

    def _add_emails(self, values):
        if not (self._top or self._body_top):
            return
        for v in values:
            v = str(v).lower().strip()
            if is_valid_email(v):
                self._emails.append(v)

    def _add_phone(self, values):
        if not (self._top or self._body_top):
            return
        for value in values:
            self._phones.append(value)

    def _add_address(self, value):
        v = sclean(value)
        c = _check_consisted_title(self.query, v, form=self.form)
        if v and (self._top or c):
            self._addresses.append(v)
        if c:
            self._body_top = True

    def _add_manager(self, tag, value=None, dir=None):
        v = sclean(dir and get_manager(' '.join([parser_sibling(t, dir) for t in [tag, tag.parent]])) or value or '')
        c = _check_consisted_title(self.query, v, form=self.form)
        m = is_valid_manager(v)
        f = is_valid_fio(v)
        if v and ( \
                c or f or
                #(self._fio and f) or
                ((self._top or self._body_top) and m)
            ):
            if v not in self._managers:
                self._managers.append(v)
            if m:
                self._fio = not f and 1 or 0
            elif f:
                self._fio = 0
        if c:
            self._body_top = True

    def _repr_tag(self, tag):
        return '%s: %s' % (tag.name, self._get_tag_attrs(tag))

    def getRating(self):
        return self._rating

    def getTagAttrs(self, tag):
        return dict(self._get_tag_attrs(tag))

    def title(self):
        try:
            value = self._soup.title.contents[0]
        except:
            return
        if self._debug:
            self.dump('Title: %s' % _out(value))
        value = value.lower()
        if _check_consisted_title(self.query, value): #, form=self.form
            self._rating += TAG_RATING['title']
            self._top += 1
        self._check_rating_of_keywords(value, rating=TAG_RATING['title'])

    def meta(self):
        for item in self._content('meta'):
            if not isinstance(item, Tag):
                continue

            attrs = self.getTagAttrs(item)
            content = attrs.get('content')
            s = ''

            if 'charset' in attrs:
                s = 'charset:%s' % attrs['charset']
            elif content:
                value = content.lower()
                if 'http-equiv' in attrs:
                    name = attrs['http-equiv'].lower()
                    if name == 'content-type':
                        s = 'Content-Type: %s' % content
                    elif name == 'x-ua-Compatible':
                        s = 'X-UA-Compatible: %s' % content
                elif 'name' in attrs:
                    name = attrs['name'].lower()
                    if name in ('description', 'keywords',):
                        s = 'Description: %s' % _out(content)
                        if _check_consisted_title(self.query, value, form=self.form):
                            self._rating += TAG_RATING[name]
                            self._top += 1
                        self._check_rating_of_keywords(value, rating=TAG_RATING[name])
                elif 'property' in attrs:
                    if _check_consisted_title(self.query, value, form=self.form):
                        self._rating += TAG_RATING['property']
                        self._top += 1
                    self._check_rating_of_keywords(value, rating=TAG_RATING['property'])
            if not s:
                s = 'meta: %s' % attrs

            if self._debug:
                self.dump(s, 2)

        if self._debug:
            self.dump('')

    def body(self):
        self._c = 0
        self.walk(self._soup, level=1) #self._soup.body

    def walk(self, tag, level=0, indent=0):
        if level > _global_html_nesting_limit or self._c > _global_html_tags_limit:
            return

        self._c += 1

        emails = []

        if tag is None:
            return
        elif isinstance(tag, NavigableString):
            value = str(tag.string or '').strip()
            if value:
                if self._fio:
                    self._add_manager(tag, value=value)
                if self.mode_string:
                    if self._debug:
                        self.dump('%sstring:[%s]' % (' '*indent, re.sub(r'\n', ' ', value)))
                    if self.mode_email and '@' in value:
                        self._add_emails(get_emails(value))
                    if self.mode_phone and is_valid_phone(value):
                        self._add_phone(get_phones(value))
                    if self.mode_address and is_valid_address(value, self.query):
                        self._add_address(get_address(value))
                    if self.mode_manager and is_valid_manager(value, self.query):
                        self._add_manager(tag, value=value)
                        self._add_manager(tag, dir='forward')
                        self._add_manager(tag, dir='back')
                    if self.mode_manager and is_valid_fio(value):
                        self._add_manager(tag, value=get_fio(value))
                value = value.lower()
                if self.query in value:
                    self._rating += TAG_RATING['default']
                self._check_rating_of_keywords(value, check=True)
            return
        elif not isinstance(tag, Tag) or tag.name in UNUSED_TAGS:
            return
        
        if self._trace and level == 1:
            self.logger.progress(line='%s[%03d]' % (tag.name, len(tag.contents)), mode='start')

        if self._debug:
            self.dump('%s%s' % (' '*indent, self._repr_tag(tag)))

        attrs = self.getTagAttrs(tag)

        if tag.name == 'a':
            href = attrs.get('href') or None
            if href:
                self._links.append(href)
                if self.mode_email and href.startswith('mailto:') and '@' in href:
                    emails.append(href.split(':')[1])

        self._add_emails(emails)

        if len(tag.contents):
            for x in tag.contents:
                if level == 1:
                    if self._trace:
                        self.logger.progress()
                    if self.use_pause:
                        time.sleep(self._pause)
                self.walk(x, level+1, indent+2)

        if self._trace and level == 1:
            self.logger.progress(mode='end')

########################################################

##  =============
##  Search Engine
##  =============

from .engines.se_ask import search as ask_search
from .engines.se_bing import search as bing_search
from .engines.se_google import search as google_search
from .engines.se_mail import search as mail_search
from .engines.se_rambler import search as rambler_search
from .engines.se_yahoo import search as yahoo_search
from .engines.se_yandex import search as yandex_search

_query_delimeter = Config['DEFAULT'].get('query_delimeter')


class SearchEngine:

    def __init__(self, engines, params, **kw):
        self.engines = engines
        self.params = params

        self.query = None
        self.logger = None

        self.db = kw.get('db') or None

        self._ask_links = 0
        self._bing_links = 0
        self._google_links = 0
        self._mail_links = 0
        self._rambler_links = 0
        self._yahoo_links = 0
        self._yandex_links = 0

        self.errorlog = kw.get('errorlog')
        self.language = kw.get('language')

        self._engines_list = ( \
            ('G', 'Google', self.google), 
            ('B', 'Bing', self.bing), 
            ('A', 'Ask', self.ask), 
            ('M', 'Mail', self.mail),
            ('R', 'Rambler', self.rambler), 
            ('H', 'Yahoo', self.yahoo),
            ('Y', 'Yandex', self.yandex), 
        )

        self._query_keywords = None
        self._main_domain = None

    def _init_state(self, logger=None):
        self.logger = logger or self.logger

        self._main_domain = ''
        self._unused_domains = []
        self._done_links = []
        self._links = []

    def update_options(self, options):
        if options:
            if 'engines' in options:
                engines = options.get('engines')
                self.engines = ''.join([x[0] for x in self._engines_list if engines.get(x[1].lower())]).upper()
            if 'modes' in options:
                modes = options.get('modes')
                for mode in SEARCH_MODES:
                    self.params[mode] = modes.get(mode)
            if 'options' in options:
                values = options.get('options')
                for key in SEARCH_OPTIONS:
                    if key in values:
                        self.params[key] = values.get(key)
            if 'count' in options:
                self.params['count'] = options['count']
            if 'depth' in options:
                self.params['depth'] = options['depth']
            if 'threshold' in options:
                self.params['threshold'] = options['threshold']

    def check_response(self, response):
        cnt = 0
        for url in response:
            self._links.append((1, url))
            #if IsDeepDebug:
            #    self.logger.out(url)
            cnt += 1
        return cnt

    def get_query(self, query):
        return self.query and ' '.join(self.query) or ''

    def set_query(self, query):
        if query:
            if _query_delimeter in query:
                query = query.split(_query_delimeter)
            else:
                query = (query, '')
            self.query = query

        if self.query and len(self.query) == 2:
            self._query_keywords = []
            for x in self.query[0].split():
                if len(x) > 3:
                    self._query_keywords.append(conv_rus_eng(x))

    def get_search_string(self, mode=None):
        keys = [x for x in self.query[0].split()]
        renosmb = re.compile(r'[\!\+]')
        renowow = re.compile(r'[\!]')

        # --> query[АЛИТ МАСТЕР::!+ООО !!!105005 !МОСКВА !ДЕНИСОВСКИЙ !23 !6 !+контакт]

        if not mode or mode == 'simple-plus':
            # --> query[ООО+АЛИТ+МАСТЕР]
            words = [re.sub(renosmb, '', x) for x in self.query[1].split()]
            search = '%s+%s' % (words[0], '+'.join(keys))

        elif mode == 'simple':
            # --> query[ООО "АЛИТ МАСТЕР"]
            words = [re.sub(renosmb, '', x) for x in self.query[1].split()]
            search = '%s %s' % (words[0], self.query[0])

        elif mode == 'no-contact':
            # --> query[ООО АЛИТ МАСТЕР 105005 МОСКВА ДЕНИСОВСКИЙ пер 23 СТР 6] # «%s»
            words = [re.sub(renosmb, '', x) for x in self.query[1].split()]
            m = '%s %s %s'
            search = m % (words[0], self.query[0], ' '.join([x for x in words[1:-1]]))

        elif mode == 'google-full':
            # --> query[ООО «АЛИТ МАСТЕР» 105005 МОСКВА ДЕНИСОВСКИЙ пер 23 СТР 6 контакт] # «%s»
            words = [re.sub(renosmb, '', x) for x in self.query[1].split()]
            s = len(self.query[0].split()) > 1 and '«%s»' or '%s'
            m = '%s ' + s + ' %s'
            search = m % (words[0], self.query[0], ' '.join([x for x in words[1:]]))

        elif mode == 'full':
            # --> query[ООО "АЛИТ МАСТЕР" 105005 МОСКВА ДЕНИСОВСКИЙ пер 23 СТР 6 контакт]
            words = [re.sub(renosmb, '', x) for x in self.query[1].split()]
            search = '%s "%s" %s' % (words[0], self.query[0], ' '.join(words[1:]).strip())

        elif mode == 'no-digits':
            # --> query[ООО "АЛИТ МАСТЕР" МОСКВА ДЕНИСОВСКИЙ пер СТР контакт]
            words = [w for w in [re.sub(renosmb, '', x) for x in self.query[1].split()] if not w.isdigit()]
            search = '%s "%s" %s' % (words[0], self.query[0], ' '.join(words[1:]).strip())

        elif mode == 'full-plus':
            # --> query[ООО+АЛИТ+МАСТЕР+105005+МОСКВА+ДЕНИСОВСКИЙ+23+6+контакт"]
            words = [re.sub(renosmb, '', x) for x in self.query[1].split()]
            search = '%s+%s' % ('+'.join(keys), '+'.join(words).strip())

        else:
            return self.get_search_string('full')

        return search

    def get_links(self):
        return self._links

    def set_links(self, links, **kw):
        if not links:
            return
        for x in links:
            self._links.append(x)
        if 'threshold' in kw:
            self.params['threshold'] = kw.get('threshold')

    def state(self):
        return ( \
            self._ask_links, self._bing_links, self._google_links, self._mail_links, self._rambler_links, self._yahoo_links, self._yandex_links)

    def search(self, query=None):
        self.set_query(query)

        for code, name, engine in self._engines_list:
            if IsDebug:
                self._links.append((-1, ':%s' % name))
            engine()

        return self.get_links()

    def brand(self, n):
        name = ''
        if n < len(self._engines_list):
            code, name, engine = self._engines_list[n]
        return name

    def iter(self, n):
        if n < len(self._engines_list):
            code, name, engine = self._engines_list[n]
            if IsDebug:
                self._links.append((-1, ':%s' % name))
            engine()

    def ask(self):
        if 'A' in self.engines:
            section = Config['ASK']
            search = self.get_search_string(section.get('search_string'))
            stop = self.params.get('ask') or section.getint('stop')

            response = ask_search(search, self.logger, errorlog,
                tld=section.get('domain'), 
                lang=self.language, 
                start=section.getint('start'), 
                stop=stop, 
                only_standard=True, 
                parser=section.get('html_parser'),
                trace=False
            )

            self._ask_links = self.check_response(response)
        else:
            self._ask_links = 0

    def bing(self):
        if 'B' in self.engines:
            section = Config['BING']
            search = self.get_search_string(section.get('search_string'))
            stop = self.params.get('ask') or section.getint('stop')

            response = bing_search(search, self.logger, errorlog,
                tld=section.get('domain'), 
                lang=self.language, 
                start=section.getint('start'), 
                stop=stop, 
                only_standard=True, 
                parser=section.get('html_parser'),
                trace=False
            )

            self._bing_links = self.check_response(response)
        else:
            self._bing_links = 0

    def google(self):
        if 'G' in self.engines:
            section = Config['GOOGLE']
            search = self.get_search_string(section.get('search_string'))
            stop = self.params.get('google') or section.getint('stop')

            response = google_search(search, self.logger, errorlog,
                tld=section.get('domain'), 
                lang=self.language, 
                start=section.getint('start'), 
                stop=stop, 
                only_standard=True, 
                parser=section.get('html_parser'),
                trace=False
            )

            self._google_links = self.check_response(response)
        else:
            self._google_links = 0

    def mail(self):
        if 'M' in self.engines:
            section = Config['MAIL']
            search = self.get_search_string(section.get('search_string'))
            stop = self.params.get('ask') or section.getint('stop')

            response = mail_search(search, self.logger, errorlog,
                tld=section.get('domain'), 
                lang=self.language, 
                start=section.getint('start'), 
                stop=stop, 
                only_standard=True, 
                parser=section.get('html_parser'),
                trace=False
            )

            self._mail_links = self.check_response(response)
        else:
            self._mail_links = 0

    def rambler(self):
        if 'R' in self.engines:
            section = Config['RAMBLER']
            search = self.get_search_string(section.get('search_string'))
            stop = self.params.get('ask') or section.getint('stop')

            response = rambler_search(search, self.logger, errorlog,
                tld=section.get('domain'), 
                lang=self.language, 
                start=section.getint('start'), 
                stop=stop, 
                only_standard=True, 
                parser=section.get('html_parser'),
                trace=False
            )

            self._rambler_links = self.check_response(response)
        else:
            self._rambler_links = 0

    def yahoo(self):
        if 'H' in self.engines:
            section = Config['YAHOO']
            search = self.get_search_string(section.get('search_string'))
            stop = self.params.get('ask') or section.getint('stop')

            response = yahoo_search(search, self.logger, errorlog,
                tld=section.get('domain'), 
                lang=self.language, 
                start=section.getint('start'), 
                stop=stop, 
                only_standard=True, 
                parser=section.get('html_parser'),
                trace=False
            )

            self._yahoo_links = self.check_response(response)
        else:
            self._yahoo_links = 0

    def yandex(self):
        if 'Y' in self.engines:
            section = Config['YANDEX']
            search = self.get_search_string(section.get('search_string'))
            stop = self.params.get('ask') or section.getint('stop')

            response = yandex_search(search, self.logger, errorlog,
                tld=section.get('domain'), 
                lang=self.language, 
                start=section.getint('start'), 
                stop=stop, 
                only_standard=True, 
                parser=section.get('html_parser'),
                trace=False
            )

            self._yandex_links = self.check_response(response)
        else:
            self._yandex_links = 0

    def callback(self, level, href):
        link = (level, href)
        if not link in self._links:
            if is_key_inside(href, self._query_keywords):
                self._links.insert(0, link)
            else:
                self._links.append(link)

    def explore(self, **kw):
        self.begin(**kw)

        try:
            while not self.is_break():
                self.next()
                self.go()
        finally:
            self.finish()

        return self._current

    def is_break(self):
        return self._is_break

    def current_state(self):
        return not self.is_break() and (self._current, len(self._links), unquote(self._url), self._level,)

    def begin(self, **kw):
        self._count = kw.get('count') or Config['DEFAULT'].getint('default_count')
        self._depth = kw.get('depth') or Config['DEFAULT'].getint('default_depth')

        self._trace = IsTrace and kw.get('trace') and True or False
        self._mode_unique = kw.get('unique')

        self._query = self.query[0].replace('"', '')
        self._keywords = self.query[1].split()

        self._output = []

        self._is_break = False
        self._is_invalid = False
        self._current = 0

        self._selenium_enabled = Config['SELENIUM'].getboolean('enabled')
        self._selenium_rating = Config['SELENIUM'].getint('rating')

        log(os.path.join(basedir, 'links.log'), [x[1] for x in self._links], mode='a+b', bom=False)

        self._done_links = []

    def next(self):
        if not len(self._links) or self._current > self._count:
            self._is_break = True
            return

        self._is_invalid = False
        self._level, self._url = self._links.pop(0)
        
        #print(unquote(self._url))
        
        if self._level > self._depth:
            self._is_invalid = True
            return

        #print(1)

        if not self._url.startswith('http') or self._level < 0:
            self._is_invalid = True
            return

        #print(2)

        if self._url in self._done_links or not is_valid_href(self._url):
            self._is_invalid = True
            return

        #print(3)

        if get_domain(self._url) in self._unused_domains:
            self._is_invalid = True
            return

        #print(4)

        if self.db is not None:
            if not self.db.isUriEnabled(self._url):
                self._is_invalid = True
                return
            domain = get_domain(self._url, 2)
            if is_value_inside(domain, self._done_links) and not self.db.isUriEnabled(self._url, 2):
                self._is_invalid = True
                return

        #print(5)

        self._so = None

    def go(self):
        if self._is_break or self._is_invalid:
            return

        if IsDebug:
            self.logger.out(self._url)

        self._alias = parser_get_alias(self._url)

        if IsDebug and is_valid_alias(self._alias):
            data = Config['OUTPUT'].get('dump_folder')
            mkdir(os.path.join(data, self._query))

            try:
                self._so = Logger(os.path.join(data, self._query, '%s.dump' % self._alias), bom=True, end_of_line=EOR)
            except:
                self._so = None

        self._current += 1

        page = Page(self._alias, self._query, self._url, self._level, self._current, self.callback, \
                    self._keywords, self._so, self._depth, **self.params)
        page._init_state(logger=self.logger)

        selenium = self._level == 0 and True or False

        started_at = datetime.datetime.now()
        err = False

        try:
            self._output = page(self._output, selenium=selenium, trace=self._trace)
            err = page.isError()
        except KeyboardInterrupt as err:
            if IsDebug:
                self.logger.out('...')
            self._is_break = True
        except:
            if self.errorlog:
                self.errorlog.write('%s:%s' % (datetime.datetime.now().strftime(Config['DEFAULT'].get('FULL_TIMESTAMP')), EOL))
                self.errorlog.write('%s%s' % (self._url, EOL))
                traceback.print_exc(file=self.errorlog)
                self.errorlog.write(EOL)
            else:
                print_exception()

            if self._so is not None:
                self._so.out(EOL)
                info = sys.exc_info()
                self._so.out('%s:%s' % (info[0], info[1]))
                traceback.print_exc(file=self._so.get_to_file())

            err = True

        if not err and not self._main_domain:
            x = page.getMainDomain()
            if x:
                self._main_domain = '.'.join(x.split('.')[-2:])

        data = page.getUrlInfo()
        spended_time = (datetime.datetime.now() - started_at).seconds

        if data and self.db is not None:
            #
            # Page data - scraping info (list):
            #   0: uri
            #   1: html_size
            #   2: parsing_time
            #   3: spended_time (total)
            #   4: rating
            #
            data[3] = spended_time
            self.db.register('uri', data)

        if not self._main_domain and (err or spended_time > _global_spended_time_limit):
            self._unused_domains.append(get_domain(self._url))
            self._current -= 1
        elif not selenium and self._selenium_enabled and page.getRating() > self._selenium_rating:
            self._links.insert(0, (0, self._url))
            self._current -= 1
        else:
            self._done_links.append(self._url)

        if self._so is not None:
            self._so.close()
            del self._so

        del page

    def get_current(self):
        return self._current

    def finish(self):
        #
        # Makes output results.
        # Returns (tuple):
        #   domain : client site domain
        #   uri    : main client site uri (if found)
        #   data   : all found items
        #   path   : path to output file
        #
        if not self._output:
            return None

        output = {}
        for mode in SEARCH_MODES:
            output[mode] = sorted([x for x in self._output if x[0] == mode], key=lambda x: x[4], reverse=True)

        domain, uri, data = self.pickup(output)

        self._init_state()

        try:
            output_path = os.path.join(Config['OUTPUT'].get('output_folder'), 'output-%s.txt' % self._query)
            self._so = Logger(output_path, bom=True, end_of_line=EOR)
        except:
            return (domain, uri, data, None)

        self._so.out('%s%s%s' % (self._query, len(self._keywords) and _query_delimeter or '', ' '.join(self._keywords) or ''))
        self._so.out(EOR)

        def _out_master(mode, values):
            #
            # Output structure:
            # values: [(v, [u1, u2, u3...]), ...]
            #     v : value
            #     u1, u2, u3 : uri where found
            #
            for x in values:
                self._so.out('>>> %s: %s' % (mode, x[0]))
            return values and True or False

        if domain:
            self._so.out('--> domain: %s' % domain)
        if uri:
            self._so.out('--> uri: %s' % uri)

        if data:
            if domain or uri:
                self._so.out(EOR)
            done = False
            for n, mode in enumerate(SEARCH_MODES):
                if _out_master(mode, data[n]):
                    done = True
            if done:
                self._so.out(EOR)
        
        self._so.out('***'+EOR)

        for mode in SEARCH_MODES:
            used = []
            for m, u, a, l, r, v in output[mode]:
                header = False
                for x in v:
                    if self._mode_unique and x in used:
                        continue
                    if not header:
                        self._so.out(parser_unquote(u))
                        self._so.out(a)
                        header = True

                    self._so.out('%s: %s' % (m, x))
                    used.append(x)

                if header:
                    self._so.out('%s:%s' % (str(l), str(r)))
                    self._so.out(EOR)

        self._output = None

        self._so.close()

        make_html(output_path)

        return (domain, uri, data, output_path)

    def pickup(self, output):
        #
        # Output data (dict, key:mode, value:list of tuples, sorted by rating):
        #   0: mode
        #   1: url
        #   2: alias
        #   3: level
        #   4: rating
        #   5: values (list)
        #
        emails= []
        phones = []
        addresses = []
        managers = []

        def _get_rating(mode, domain, force=False):
            w = 0

            # Совпадает ли с основным доменом
            if self._main_domain and domain in self._main_domain:
                w += 10000

            # Суммарный рейтинг в списке найденных значений
            for x in output[mode]:
                for v in x[5]:
                    if domain in v:
                        w += x[4]
                if force and domain in x[1]:
                    w += x[4]

            # Встречается ли в просмотренных URI
            names = domain.split('.')
            for x in self._done_links:
                # домен целиком
                if domain in get_domain(x):
                    w += 1000
                # или домен второго уровня
                elif domain in x or names[0] in x:
                    w += 100

            return w

        def _high(weights, any=None):
            if not weights:
                return []

            if len(weights) == 1:
                return weights

            minw = weights[-1][1]
            maxw = weights[0][1]

            # Процентовка
            wp = maxw/100

            p = None
            for n, x in enumerate(weights):
                d, w = x
                # превышение выше заданного лимита
                if p and (p-w)/wp > _global_high_weight_domain:
                    break
                # сравниваем соседей
                else:
                    p = w

            if n >= len(weights) and any:
                return [x for x in weights if x[1]]
            
            return weights[:n]

        def _split_uri(value):
            words = [x for x in parse_qs(re.sub(r'(http[s]?://)([a-zA-Z0-9_.+-\/]+)', r'\2', value or ''))]
            exists = 1
            n = 0
            while words and n <= len(words):
                word = words.pop(0)
                exists = 0
                for s in '/._-?':
                    if s in word:
                        words += [x for x in word.split(s) if x and x not in words]
                        exists = 1
                        n = 0
                if not exists and word not in words:
                    words.append(word)
                n += 1
            return sorted(list(set(words)))

        def _count_value(mode, value):
            w = 0
            for x in output[mode]:
                for v in x[5]:
                    if value.lower() in v.lower():
                        w += 1
            return w

        def _get_manager(value):
            if not is_valid_info(value):
                return ''
            return get_manager(value)

        def _get_fio(value):
            if not is_valid_info(value):
                return ''
            return get_fio(value)

        links = sorted(self._done_links)

        # Попробуем выяснить, существует ли сайт - основной домен у клиента
        domain = ''
        uri = ''

        def _scheme_top_email_domain():
            domain = ''

            # Отберем все почтовые домены (ds) и просчитаем их веса (weights)
            ds = set([get_email_domain(v) for x in output['email'] for v in x[5] if v])
            domains = dict([(x, _get_rating('email', x)) for x in ds])
            weights = sorted(domains.items(), key=itemgetter(1), reverse=True)

            # Существует ли очевидный лидер
            tops = _high(weights)

            # Это очень вероятно, если лидер один
            if len(tops) == 1:
                domain = weights[0][0]

            return domain

        def _scheme_more_often_keyword():
            keyword = ''

            # Отберем все ключевые слова в URI
            words = []
            
            for x in links:
                words = list(set(words + _split_uri(x)))

            # Подсчитаем кол-во вхождений каждого слова в URIs
            words = dict([(x, 0) for x in words if len(x) > 3])
            for w in words:
                for x in links:
                    if w in x:
                        words[w] += 1

            weights = sorted(words.items(), key=itemgetter(1), reverse=True)

            # Существует ли очевидный лидер
            tops = _high(weights)

            # Это очень вероятно, если лидер один
            if len(tops) == 1:
                keyword = weights[0][0]

            return keyword

        def _scheme_more_often_phones():
            phones = []

            # Отберем все телефоны и подсчитаем кол-во совпадений
            ns = set([(v, u) for m, u, a, l, r, x in output['phone'] for v in x if v])
            
            # Словарь: телефон:v -> рейтинг
            numbers = dict([(v, 0) for v, u in ns])
            
            # Словарь: телефон:v -> URL
            urls = dict([(v, u) for v, u in ns])

            # Проверим совпадения также в адресах и в данных о менеджерах
            for x in numbers:
                numbers[x] += _count_value('phone', x)
                numbers[x] += _count_value('address', x)
                numbers[x] += _count_value('manager', x)

            weights = sorted(numbers.items(), key=itemgetter(1), reverse=True)

            # Существует ли очевидный лидер
            tops = _high(weights)

            # Это очень вероятно, если лидеров меньше пяти
            if len(tops) < 5:
                for v, w in tops:
                    phones.append((v, urls[v]))

            return phones

        def _scheme_managers_by_keywords():
            managers = []

            urls = {}
            # Проверим совпадения ключевых слов в данных о менеджерах
            for w, key in MANAGER_KEYS:
                for x in output['manager']:
                    r = 0
                    u = x[1]
                    for v in x[5]:
                        if key in v.lower():
                            r += 1 #w*x[4]
                    if u in urls:
                        urls[u] = max(urls[u], r)
                    else:
                        urls[u] = r

            # Рассчитаем веса источников
            weights = sorted(urls.items(), key=itemgetter(1), reverse=True)

            # Существует ли очевидный лидер (по рейтингу ключевого слова:r)
            tops = _high(weights, any=True)

            # Словарь: ФИО:s -> (url, должность:p)
            items = {}

            # Все словосочетания с вероятным ФИО
            for url, w in tops:
                for x in output['manager']:
                    if x[1] == url:
                        p = ''
                        s = ''
                        for v in x[5]:
                            if not p:
                                p = _get_manager(v)
                            if not s:
                                s = _get_fio(v)
                            if s and p:
                                break
                        if s and ((s in items and p and ( \
                                not items[s][1] or len(p) > len(items[s][1]))) or \
                            not s in items):
                            items[s] = (url, p)

            # Словарь: ФИО:s -> кол-во повторений:w
            ms = dict([(s, 0) for s in items])

            # Кол-во повторений
            for x in items:
                r = 0
                for m in ms:
                    if x in m:
                        r += 1
                ms[x] = r

            # Существует ли очевидный лидер (по ФИО)
            weights = sorted(ms.items(), key=itemgetter(1), reverse=True)

            # Отберем упоминаемые чаще всех
            tops = _high(weights, any=True)

            # Пытаемся отобрать не более 3-х наиболее часто встречающихся словосочетаний ФИО
            if len(tops):
                used = ''
                for m, w in tops:
                    if len(managers) == 3:
                        break
                    if m in used:
                        continue

                    # Наиболее полное словосочетание: 'Должность Фамилия Имя Отчество'
                    s = ''
                    for x in items:
                        if m in x and len(x) > len(s):
                            s = x
                    if m == s and items[m][1] and not items[m][1] in s:
                        s = ('%s %s' % (items[m][1], s)).strip()
                    if s:
                        managers.append((s, items[m][0]))
                        used += '%s|' % s

            return managers

        def _scheme_managers_by_fio():
            managers = []

            # Словарь: ФИО:s -> url
            urls = {}

            # Словарь: ФИО:s -> рейтинг источника*кол-во повторений:w
            ms = {}

            # Найдем все ФИО
            for x in output['manager']:
                u = x[1]
                for v in x[5]:
                    s = _get_fio(v)
                    if s:
                        if not s in urls:
                            urls[s] = []
                        if not u in urls[s]:
                            urls[s].append(u)
                        if not s in ms:
                            ms[s] = 0
                        ms[s] += x[4]

            # Рассчитаем веса источников
            weights = sorted(ms.items(), key=itemgetter(1), reverse=True)

            # Существует ли очевидный лидер (по ФИО:s)
            tops = _high(weights, any=True)

            # Словарь: ФИО:s -> (url, должность:p)
            items = {}

            # Все словосочетания с вероятным ФИО
            for s, w in tops:
                for url in set(urls[s]):
                    for x in output['manager']:
                        if x[1] == url:
                            p = ''
                            for v in x[5]:
                                if not p:
                                    p = _get_manager(v)
                                #if p:
                                #    break
                                if p and ((s in items and p and ( \
                                        not items[s][1] or len(p) > len(items[s][1]))) or \
                                    not s in items):
                                    items[s] = (url, p)
                                    p = ''

            # Словарь: ФИО:s -> кол-во повторений:w
            ms = dict([(s, 0) for s in items])

            # Кол-во повторений
            for x in items:
                r = 0
                for m in ms:
                    if x in m:
                        r += 1
                ms[x] = r

            # Существует ли очевидный лидер (по ФИО)
            weights = sorted(ms.items(), key=itemgetter(1), reverse=True)

            # Отберем упоминаемые чаще всех
            tops = _high(weights, any=True)

            # Пытаемся отобрать не более 3-х наиболее часто встречающихся словосочетаний ФИО
            if len(tops):
                used = ''
                for m, w in tops:
                    if len(managers) == 3:
                        break
                    if m in used:
                        continue

                    # Наиболее полное словосочетание: 'Должность Фамилия Имя Отчество'
                    s = ''
                    for x in items:
                        if m in x and len(x) > len(s):
                            s = x
                    if m == s and items[m][1] and not items[m][1] in s:
                        s = ('%s %s' % (items[m][1], s)).strip()
                    if s:
                        managers.append((s, items[m][0]))
                        used += '%s|' % s

            return managers

        # Наиболее вероятное доменное имя
        domain = _scheme_top_email_domain() or self._main_domain

        # Наиболее употребительное ключевое слово
        word = _scheme_more_often_keyword()

        # ------------
        #   Main URI
        # ------------

        if domain:
            for x in links:
                if domain in get_domain(x):
                    uri = x
                    break

        # -------------------
        #   Почтовые адреса
        # -------------------

        if not (domain or word):
            # Emails: в адресе совпадает название компании
            emails = [(x, u) for m, u, a, l, r, v in output['email'] for x in v if \
                _check_consisted_email(self._query, x)
            ]
        elif domain and word:
            # Emails: в адресе совпадает домен или ключевое слово
            emails = [(x, u) for m, u, a, l, r, v in output['email'] for x in v if \
                (domain in x) and (word in u)
            ]
        elif domain:
            # Emails: в адресе совпадает домен или в URI совпадает ключевое слово 
            emails = [(x, u) for m, u, a, l, r, v in output['email'] for x in v if \
                (domain in x) or (domain in u)
            ]
            # Phones: телефон из доменного сайта
            phones = [(x, u) for m, u, a, l, r, v in output['phone'] for x in v if \
                (domain in u)
            ]
        elif word:
            # Emails: адрес из доменного сайта
            emails = [(x, u) for m, u, a, l, r, v in output['email'] for x in v if \
                (domain in u)
            ]

        if not len(emails):
            emails = [(x, u) for m, u, a, l, r, v in output['email'] for x in v if \
                (x and is_valid_email(x))
            ]

        def _filter_unique(items):
            out = []
            if items:
                for v1, u1 in items:
                    #ex = 0
                    #for v2, u2 in items:
                    #    if v1 != v2 and v1 in v2:
                    #        ex = 1
                    #        break
                    if not is_key_inside(v1, [v for v, u in items]):
                        out.append((v1, u1))
            return out

        def _check_unique(items):
            out = {}
            if items:
                for v, u in items:
                    if not v in out:
                        out[v] = []
                    if not u in out[v]:
                        out[v].append(u)
            return out and list(out.items()) or []

        emails = _check_unique(emails)

        # ------------
        #   Телефоны
        # ------------

        # Выберем часто встречающиеся телефонные номера
        phones = _scheme_more_often_phones()

        # Дополним
        if not (domain or word):
            pass
        elif domain and word:
            pass
        elif domain:
            # Phones: телефон из доменного сайта
            phones += [(x, u) for m, u, a, l, r, v in output['phone'] for x in v if \
                (domain in u)
            ]
        elif word:
            pass

        phones = _check_unique(_filter_unique(phones)) or []

        # ---------------------
        #   ФИО руководителей
        # ---------------------

        if Config['GLOBAL'].get('manager_pickup_scheme') == 'keywords':
            managers = _scheme_managers_by_keywords()
        else:
            managers = _scheme_managers_by_fio()

        return domain, uri, (emails, phones, addresses, managers)