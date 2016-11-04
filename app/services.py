# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import datetime
import re

from operator import itemgetter

import requests

if sys.version_info[0] > 2:
    from bs4 import BeautifulSoup, Tag, NavigableString
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
else:
    from BeautifulSoup import BeautifulSoup, Tag, NavigableString
    from urllib2 import Request, urlopen, HTTPError

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from config import (
     Config, ERRORLOG as errorlog, IsDebug, IsDeepDebug, IsTrace, basedir,
     SEARCH_ENGINES, SEARCH_MODES,
     KAD_SERVICES, KAD_CASE_KEYS, KAD_PARTICIPANT_KEYS)

from .core import get_page_agent, SearchEngine
from .dbase import DBConnector
from .logger import print_to, print_exception
from .utils import spent_time, get_domain, get_upload_dumps, make_cookiejar_from_dict

IsSelfTest = 0
IsUpload = 0

_default_progress = (0, 0, '')

_const_default_language = Config['DEFAULT'].get('default_language')
_const_min_word_len = Config['DEFAULT'].getint('const_min_word_len')
_const_query_exc_words = Config['DEFAULT'].get('query_exc_words')

_global_requests_timeout_connect = Config['GLOBAL'].getfloat('requests_timeout_connect') or 3.05
_global_requests_timeout_read = Config['GLOBAL'].getfloat('requests_timeout_read') or 7.0

_dumps = [ \
    ('20151013155314', ('20151013155328',),),
    ('20151013160659', ('20151013160706',),),
    ('20151013161639', ('20151013161639',),),
    ('20151014022955', ('20151014022955',),),
]

# [links]:(ob):max_pages:threshold:id
_test_queries = ( \
    (
        [
            (1, 'https://sbis.ru/contragents/7708787324/770801001'),
        ],
        ('ООО Рибейт', '107140, Москва, пер. Леснорядский д.10, корп.2',),
        1, 0, '578:599:901:1',
    ),
)


class BaseProxy(object):

    # --------------------------------------------
    # Free Proxy list: http://www.samair.ru/proxy/
    # --------------------------------------------

    def __init__(self, url, db, callback=None):
        self.url = url
        self.db = db
        self.callback = callback

    def _init_state(self):
        self._proxies = {}
        self._done_proxies = []
        self._ip = []
        self._current_ip = None
        self._valid_proxy = None

    def __call__(self, pages, prefix='proxy', check_online=False):
        self._init_state()
        
        self.pages = pages
        self.prefix = prefix
        self.check_online = check_online
        self.updated = False

        self._page = 0

    def _init_proxy(self):
        return {'kind':None, 'land':None, 'response':0, 'online':None}

    def _get_response(self, x):
        t = datetime.datetime.now()
        return self.check_proxy(x), spent_time(t)

    def _update(self):
        #
        # Get a page with proxy list, check proxy state (online/offline) and make sorted list by less response time
        #
        if not self.url:
            return

        if self._page < self.pages:
            self._page += 1
            p = self.get_proxies('%s/%s-%02d.htm' % (self.url, self.prefix, self._page))
            if p is None:
                return
            self._proxies.update(p)
        else:
            self.updated = True

        if self.check_online and self._proxies:
            for x in self._proxies:
                if x['online'] is None:
                    self._proxies[x]['online'], self._proxies[x]['response'] = self._get_response(x)

        self._ip = sorted([x for x in self._proxies if not x in self._done_proxies and \
                (not self.check_online or self._proxies[x]['online'])], 
            key=itemgetter(1))

    def check_proxy(self, proxy):
        #
        # Check if proxy online
        #
        online = False
        ipinfo = {}

        proxies = {'http' : 'http://%s' % proxy}

        try:
            text = requests.get('http://ipinfo.io/json', proxies=proxies).text
            try:
                ipinfo = json.loads(text)
            except ValueError:
                pass
        except requests.ConnectionError as e:
            status = 'No connection to proxy server possible, aborting: {}'.format(e)
        except requests.Timeout as e:
            status = 'Timeout while connecting to proxy server: {}'.format(e)
        except Exception as e:
            status = 'Unknown exception: {}'.format(e)

        if 'ip' in ipinfo and ipinfo['ip'] and (self.callback is None or self.callback(proxy)):
            online = True
            status = 'Proxy is working.'
        else:
            status = 'Proxy check failed: %s is not used while requesting' % proxy

        if IsDebug:
            print('%s[%s]' % (online and '+' or '-', proxy))

        return online

    def open(self, url, headers={}):
        request = Request(url)
        request.add_header('User-Agent', get_page_agent())

        for x in headers:
            request.add_header(x, headers[x])
    
        try:
            response = urlopen(request, timeout=10.0)
            html = response.read()
            response.close()
        except:
            return '', None
    
        if html:
            soup = BeautifulSoup(html, Config['DEFAULT'].get('default_html_parser'))
        else:
            soup = None
    
        return html, soup

    def get_ports(self, url):
        #
        # Get content of css (port list)
        #
        if IsDebug:
            print('get_ports: %s' % url)

        html, soup = self.open(url, headers={ \
            'Accept'          : 'text/css,*/*;q=0.1',
            'Accept-Language' : 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Referer'         : 'http://www.samair.ru/proxy/',
            'Connection'      : 'keep-alive',
            'Pragma'          : 'no-cache',
            'Cache-Control'   : 'max-age=0',
        })
        
        css = {}
        for x in soup.contents[0].split('\n'):
            try:
                c, v = re.sub(r'after\s+{content:"([\d]+)"}', r'\1', x).split(':')
                css[c[1:]] = v
            except:
                pass

        return css

    def get_proxies(self, url):
        #
        # Get content of the page (proxy list)
        #
        if IsDebug:
            print('get_proxies: %s' % url)

        html, soup = self.open(url, headers={ \
            'Accept'          : 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language' : 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Referer'         : 'http://www.samair.ru/proxy/',
            'Connection'      : 'keep-alive',
            'Cache-Control'   : 'max-age=0',
        })
        
        if soup is None:
            return None # 'Error-1'
        #
        # Check css link tag and find /styles/xxxxx.css inside (::after is a port)
        #
        href = ''
        for item in soup.findAll('link'):
            attrs = dict(item.attrs)
            if not ('type' in attrs and 'href' in attrs):
                continue
            if attrs['type'] != 'text/css':
                continue
            href = attrs['href']
            if not href.startswith('/styles/'):
                href = ''
                continue
            break

        css = {}
        #
        # Get content of the css
        #
        if href:
            url_css = '%s%s' % (get_domain(url)[:-1], href)

            if IsDebug:
                print(url_css)

            css = self.get_ports(url_css)
        #
        # Find <table id="proxylist"> inside the page
        #
        table = soup.find('table', attrs={'id':'proxylist'})

        if not table:
            return None # 'Error-3'
        #
        # Get content of the table: proxy|type|date|land ...
        #
        proxies = {}
        for tr in table.findAll('tr'):
            if tr is None or len(tr.contents) != 4:
                continue

            if href:
                # Has port in css
                p = ''
                for tag in tr.findAll('span'):
                    if tag is None or not isinstance(tag, Tag):
                        continue
                    if not 'class' in tag.attrs:
                        continue
                    c = tag.attrs['class'][0].replace('.', '')
                    if not c in css:
                        continue
                    v = str(tag.string or '').strip()
                    if c and v:
                        p = '%s%s' % (v, css.get(c))
                        break
            else:
                # ip & port inline
                try:
                    p = tr.contents[0].string.strip()
                except:
                    p = None

            if p is None or p in self._done_proxies:
                continue

            # Register proxy
            kind = tr.contents[1].string.strip()
            land = tr.contents[3].string
            if p and kind and land:
                proxies[p] = self._init_proxy()
                proxies[p]['kind'] = kind
                proxies[p]['land'] = land

        return proxies

    def get(self):
        #
        # Returns the next valid proxy from self DB or a free page list
        #
        self._valid_proxy = self.db.getValidProxy(self._valid_proxy)

        if self._valid_proxy is not None:
            x = self._valid_proxy.address
            self._done_proxies.append(x)
            self._current_ip = x
            return self._current_ip
        else:
            self._valid_proxy = -1

        if not self._ip or len(self._ip) == 0:
            self._current_ip = None
            if not self.updated:
                self._update()
            else:
                return None

        if len(self._ip) > 0:
            self._current_ip = self._ip.pop(0)
        return self._current_ip

    def register(self):
        if not self._current_ip:
            return
        x = self._current_ip
        if not x in self._proxies:
            self._proxies[x] = self._init_proxy()
        self._proxies[x]['online'], self._proxies[x]['response'] = self._get_response(x)
        self.db.register('proxy', (x, self._proxies.get(x)))


class BaseService(object):
    
    def __init__(self, alias, consumer, **kw):
        self.consumer = consumer

        self.logger = None
        self.db = None
        self.proxies = None
        self.selenium_proxies = None

        self._debug = kw.get('debug') and True or False
        self._trace = kw.get('trace') and True or False

        # Mandatory progress attributes
        self._progress = None
        self._stage = 0
        self._ready = False

        self._timeout = kw.get('timeout') or 3.0
        self._cookies = None
        self._headers = None

        self._page = 0
        self._proxy = None

    def _init_state(self, logger=None, with_proxy=False, proxy_callback=None):
        self.logger = logger

        self.db = DBConnector(debug=self._debug, trace=self._trace)

        if with_proxy:
            self._proxy = BaseProxy('http://www.samair.ru/proxy-by-country', self.db, proxy_callback)
            self._proxy(10, prefix='Russian-Federation', check_online=False)

        self._progress = { \
            'top'    : list(_default_progress).copy(),
            'bottom' : list(_default_progress).copy(),
            'found'  : 0,
            'ready'  : 0
        }

    def extract_cookies(self, response, request):
        return
        #try:
        #    self._cookies.extract_cookies(response, request)
        #except:
        #    print_exception()

    def getState(self):
        return self._progress

    def isReady(self):
        return self._ready

    def init(self):
        self.db.open_session()

    def run(self):
        pass


class Kad(BaseService):

    #_agent = 'Mozilla/5.0 (Windows NT 6.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36'
    #_agent = 'Mozilla/5.0 (Windows NT 6.0; rv:40.0) Gecko/20100101 Firefox/40.0'
    _agent = 'Mozilla/5.0 (Windows NT 6.0; rv:41.0) Gecko/20100101 Firefox/41.0'
    _base_url = 'http://kad.arbitr.ru/'

    def __init__(self, consumer, **kw):
        BaseService.__init__(self, 'kad', consumer, **kw)

        self.date_from = kw.get('date_from')
        self.pages_count = kw.get('pages_count') or 25
        self.case_type = kw.get('case_type') or 'G'
        self.court = kw.get('court') or 'MSK'

        self._use_selenium = kw.get('selenium') or True
        self._with_proxy = kw.get('with_proxy') or True
        self._tmp = None
        self._current_dump = None
        self._dump_prefix = None

        self._count = 0
        self._max = 0

        self.cases = []
        self.documents = []

        self.case_id = None
        self.document_id = None

    def _init_state(self, logger=None, **kw):
        super()._init_state(logger, with_proxy=self._with_proxy, proxy_callback=self._check_response)

        if IsDeepDebug:
            self.logger.out('init_state: %s %s %s %s' % (self.date_from, self.pages_count, self.case_type, self.court))

        self._tmp = os.path.join('./', Config['OUTPUT'].get('upload_folder'))

        if IsSelfTest:
            self._dumps = IsUpload and get_upload_dumps(self._tmp) or _dumps

        if self._with_proxy:
            self._set_proxy(self._proxy.get())

        self._progress['top'][2] = 'Инициализация сервиса...'
        self._ready = False

        self._response = None

    def _set_proxy(self, proxy):
        if proxy:
            self.proxies = {'http': 'http://%s' % proxy}
            self.selenium_proxies = ['--proxy=%s' % proxy, '--proxy-type=http']
        else:
            self.proxies = self.selenium_proxies = None

    def _is_success(self):
        return self._response is not None and self._response.status_code == 200 and True or False

    def _get_response(self, url, data=None, headers=None, cookies=None, code=None, message=None):
        self._response = None

        try:
            self._response = requests.get(url, json=data, headers=headers, cookies=cookies, proxies=self.proxies, 
                timeout=(_global_requests_timeout_connect, _global_requests_timeout_read))
        except:
            print_exception()

        if not self._is_success():
            if self._with_proxy:
                self._set_proxy(self._proxy.get())
            if not self.proxies:
                self.consumer.set_error(code % (self._response is not None and self._response.status_code or '?'), message)
            else:
                self._progress['top'][2] = 'Proxy: %s' % self.proxies.get('http')
            return

    def _check_response(self, proxy):
        self._set_proxy(proxy)
        try:
            self._response = requests.get(self._base_url, proxies=self.proxies,
                timeout=2*_global_requests_timeout_read)
        except:
            return False
        return self._is_success()

    def _stage_0(self):
        url = self._base_url

        if IsSelfTest:
            time.sleep(3.0)

        elif self._use_selenium:
            driver = webdriver.PhantomJS( \
                #service_args=self.selenium_proxies,
                #desired_capabilities=dict(DesiredCapabilities.PHANTOMJS)
            )
            driver.set_page_load_timeout(Config['DEFAULT'].get('default_timeout'))
            driver.get(url)
            cookies = driver.get_cookies()
            driver.quit()
            self._cookies = make_cookiejar_from_dict(cookies)

        else:
            #response = requests.get(url, proxies=self.proxies)
        
            #if response is None or response.status_code != 200:
            #    code = '%s [%s]' % ('Error-1', response is not None and response.status_code or '?')
            #    self.consumer.set_error(code, 'Инициализация сервиса не выполнена.')
            #    return

            self._get_response(url, 
                code='Error-0 [%s]', message='Инициализация сервиса не выполнена.')

            if not self._is_success():
                return

            self._cookies = self._response.cookies

    def _stage_1(self):
        #
        # Run stage 1 (top progress)
        #
        if IsSelfTest:
            n = self._page < len(self._dumps) and self._page or 0
            self._current_dump = self._dumps[n]
        else:
            self._dump_prefix = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

        time.sleep(self._timeout)

        if IsDeepDebug:
            self.logger.out('stage 1')

        try:
            self.search()
        except:
            print_exception()

    def _stage_2(self):
        #
        # Run stage 2 (bottom progress)
        #
        time.sleep(0.1)

        if IsDeepDebug:
            self.logger.out('stage 2')

        case = self.cases[self._count]

        self.case_id = case['CaseId']

        try:
            self.load_card()
            self.load_documents()
        except:
            print_exception()

        if IsSelfTest:
            case_id = len(self.documents) and self.documents[0].get('CaseId')
            if case_id:
                for x in self.cases:
                    if case_id == x['CaseId']:
                        case = x
                        self.case_id = case_id
                        break
            if self.case_id != case_id:
                return

        elif not self._is_success:
            return

        self.register(case)

        if self._with_proxy:
            self._proxy.register()

        if IsDeepDebug:
            self.logger.out('OK')

    def init(self):
        #
        # Init next (regular) step
        #
        super().init()

        if self._progress['top'][1]:
            self._ready = True
        else:
            self._stage_0()

    def progress(self):
        self.consumer.progress()

    def top_progress(self):
        self._progress['top'][2] = 'Загрузка картотеки (стр. %s) ...' % self._page
        self.progress()

    def bottom_progress(self):
        if IsSelfTest:
            self._progress['bottom'][2] = 'Дело %s из %s' % (self._count, self._max)
        else:
            self._progress['bottom'][2] = 'Дело %s %s' % ( \
                self.cases[self._count]['CourtName'], self.cases[self._count]['CaseNumber'])
        self.progress()

    def run(self):
        #
        # Main process controller
        #
        if self._stage == 0:
            if not self._progress['top'][1] or self._progress['top'][0] < self._progress['top'][1]:
                self.top_progress()

                if not self._page or self._is_success():
                    self._page += 1

                self._stage_1()

                if not self._is_success():
                    return

                self._count = 0
                self._stage = 1
            else:
                self.consumer.finish()
                self.consumer = None
                self._stage = 0
        else:
            if self._count < self._max:
                if self.consumer.getStop():
                    return
                self.bottom_progress()

                self._stage_2()

                if not self._is_success():
                    return

                self._progress['bottom'][0] += 1
                self._count += 1
            else:
                self._progress['top'][0] += 1
                self._stage = 0

    def register(self, case):
        #
        # Register *case* data in DB
        #
        if IsDeepDebug:
            self.logger.out('register [%s]' % self.case_id)

        claim = 0
        started = False
        for document in self.documents:
            if document.get('CaseId') != self.case_id:
                continue
            if 'ClaimSum' in document:
                claim = max(claim, float(document['ClaimSum']))
            if 'IsStart' in document:
                started = True

        found = self.db.register('case', case, court=self.court, code=self.case_type, claim=claim, started=started)

        self._progress['found'] += found

    def search(self):
        # ---------------------------
        # Загрузка страницы картотеки
        # ---------------------------
        self.cases = []

        if IsDeepDebug:
            self.logger.out('search page %s' % self._page)

        h = {}
        h['User-Agent']=self._agent
        h['Accept']='application/json, text/javascript, */*'
        h['Accept-Language']='ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3'
        h['Accept-Encoding']='gzip, deflate'
        h['Content-Type']='application/json; charset=UTF-8'
        h['X-Requested-With']='XMLHttpRequest'
        h['x-date-format']='iso'
        h['Referer']=self._base_url
        h['Content-Length']=128
        h['Connection']='keep-alive'
        h['Pragma']='no-cache'
        h['Cache-Control']='no-cache'

        headers = h.copy()

        data = {
            "Page":self._page or 1,
            "Count":self.pages_count,
            "Courts":[self.court],
            "DateFrom":self.date_from,
            "DateTo":None,
            "Sides":[],
            "Judges":[],
            "CaseType":self.case_type,
            "CaseNumbers":[],
            "WithVKSInstances":False
        }

        url = self._base_url + KAD_SERVICES['getInstances']

        if IsSelfTest:
            with open(os.path.join(self._tmp, '%s.cases.dump' % self._current_dump[0])) as si:
                out = json.load(si)
        else:
            #response = requests.get(url, json=data, headers=headers, cookies=self._cookies, proxies=self.proxies)

            #if response is None or response.status_code != 200:
            #    code = 'Kad Search Error-1 [%s]' % (, response is not None and response.status_code or '?')
            #    self.consumer.set_error(code, 'Загрузка страницы картотеки не выполнена.')
            #    return

            self._get_response(url, data, headers, cookies=self._cookies, 
                code='Search Error-1 [%s]', message='Загрузка страницы картотеки не выполнена.')

            if not self._is_success():
                return

            self.extract_cookies(self._response, self._response.request)

            html = self._response.text

            out = json.loads(html)

            if self._dump_prefix:
                json.dump(out, open(os.path.join(self._tmp, '%s.cases.dump' % self._dump_prefix), 'w+'), indent=4)

        if not out or not 'Result' in out:
            code = 'no results'
            self.consumer.set_error(code, 'Нет данных.')
            return

        res = out['Result']

        total_count = int(res['TotalCount'])
        pages_count = int(res['PagesCount'])
        page_size = res['PageSize']

        for n, item in enumerate(res['Items']):
            self.cases.append({ \
                'Judge'           : item['Judge'],
                'CaseId'          : item['CaseId'],
                'CaseNumber'      : item['CaseNumber'], 
                'CaseType'        : item['CaseType'],
                'CourtName'       : item['CourtName'], 
                'Date'            : item['Date'],
                'IsSimpleJustice' : item['IsSimpleJustice'],
                'Plaintiffs'      : item['Plaintiffs']['Participants'],
                'Respondents'     : item['Respondents']['Participants']
            })

        self._max = len(self.cases)

        if not self._progress['top'][1]:
            self._progress['top'][0] = 0
            self._progress['top'][1] = pages_count

        self._progress['bottom'] = [0, self._max, '']

    def load_card(self):
        # -----------------------------------------
        # Загрузка html-контента дела: self.case_id
        # -----------------------------------------
        self.document_id = None

        if IsDeepDebug:
            self.logger.out('load card [%s]' % self.case_id)

        h = {}
        h['User-Agent']=self._agent
        h['Accept']='text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        h['Accept-Language']='ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3'
        h['Accept-Encoding']='gzip, deflate'
        h['Referer']=self._base_url
        h['Connection']='keep-alive'
        h['Cache-Control']='max-age=0'

        headers = h.copy()

        url = self._base_url + KAD_SERVICES['getCard'] + '/' + self.case_id

        if IsSelfTest:
            self.document_id = str(self._progress['bottom'][0])
        else:
            #response = requests.get(url, headers=headers, cookies=self._cookies, proxies=self.proxies)
            
            #if response is None or response.status_code != 200:
            #    code = '%s [%s]' % ('Load Card Error-1', response is not None and response.status_code or '?')
            #    self.consumer.set_error(code, 'Не выполнена загрузка *дела* [%s].' % self.case_id)
            #    return

            self._get_response(url, None, headers, cookies=self._cookies, 
                code='Load Card Error-1 [%s]', message='Не выполнена загрузка *дела* [%s].' % self.case_id)

            if not self._is_success():
                return

            self.extract_cookies(self._response, self._response.request)

            html = self._response.text

            soup = BeautifulSoup(html, Config['DEFAULT'].get('default_html_parser'))
            
            tag = soup.find('input', attrs={'class':"js-instanceId"})
                
            if not tag:
                code = '%s [%s]' % ('Load Card Error-2', self._response is not None and self._response.status_code or '?')
                self.consumer.set_error(code, 'Не найден тег *документы дела* [%s].' % self.case_id)
                return

            self.document_id = tag.attrs['value']

    def load_documents(self):
        # ------------------------------------------
        # Загрузка документов дела: self.document_id
        # ------------------------------------------
        self.documents = []

        if not self.document_id:
            return

        if IsDeepDebug:
            self.logger.out('load documents [%s]' % self.document_id)

        h = {}
        h['User-Agent']=self._agent
        h['Accept']='application/json, text/javascript, */*'
        h['Accept-Language']='ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3'
        h['Accept-Encoding']='gzip, deflate'
        h['Content-Type']='application/json'
        h['X-Requested-With']='XMLHttpRequest'
        h['Referer']='%sKad/Card' % self._base_url
        h['Connection']='keep-alive'

        headers = h.copy()

        url = self._base_url + KAD_SERVICES['getInstanceDocumentsPage'] + '?id=' + self.document_id + '&withProtocols=true&perPage=30&page=1'

        if IsSelfTest:
            if len(self._current_dump[1]) <= self._count:
                return

            with open(os.path.join(self._tmp, '%s-%s.documents.dump' % ( \
                      self._current_dump[0], self._current_dump[1][self._count]))) as si:
                out = json.load(si)
        else:
            #response = requests.get(url, headers=headers, cookies=self._cookies, proxies=self.proxies)
            
            #if response is None or response.status_code != 200:
            #    code = '%s [%s]' % ('Load Documents Error-1', response is not None and response.status_code or '?')
            #    self.consumer.set_error(code, 'Не выполнена загрузка *документов дела* [%s].' % self.document_id)
            #    return

            self._get_response(url, None, headers, cookies=self._cookies, 
                code='Load Documents Error-1 [%s]', message='Не выполнена загрузка *документов дела* [%s].' % self.document_id)

            if not self._is_success():
                return

            self.extract_cookies(self._response, self._response.request)

            html = self._response.text

            out = json.loads(html)

            if self._dump_prefix:
                json.dump(out, open(os.path.join(self._tmp, '%s-%s.documents.dump' % ( \
                    self._dump_prefix, self.document_id)), 'w+'), indent=4)

        if not out:
            code = '%s [%s]' % ('Load Documents Error-2', self._response is not None and self._response.status_code or '?')
            self.consumer.set_error(code, 'Нет *документов дела* [%s].' % self.document_id)
            return

        res = out['Result']

        for n, item in enumerate(res['Items']):
            self.documents.append({ \
                'AdditionalInfo' : item['AdditionalInfo'],
                'CaseId'         : item['CaseId'],
                'ClaimSum'       : item['ClaimSum'], 
                'CourtTag'       : item['CourtTag'], 
                'CourtName'      : item['CourtName'],
                'DisplayDate'    : item['DisplayDate'], 
                'IsStart'        : item['IsStart'],
                'Declarers'      : item['Declarers']
            })


class SearchData(BaseService):

    def __init__(self, consumer, **kw):
        BaseService.__init__(self, 'search-data', consumer, **kw)

        self._options = None
        self._params = kw.get('params') or {}

        self._id = None
        self._company = ''
        self._query = ''

        self._total_items = 0
        self._max_pages = 0
        self._count = 0
        self._max = 0

    def _init_state(self, logger=None, **kw):
        super()._init_state(logger)
        
        self._params.update({ \
            'debug'  : IsDebug, 
            'trace'  : IsTrace, 
            'top'    : True, 
            'unique' : True, 
            'string' : True, 
            'lang'   : _const_default_language, 
            'pause'  : 0,
        })

        self.engine = SearchEngine(None, self._params, db=self.db, language=_const_default_language)

        if IsDeepDebug:
            self.logger.out('init_state')

        self._progress['top'][0] = 0
        self._progress['top'][2] = 'Инициализация сервиса...'
        self._search_done = False
        self._ready = False

        self._links = None

    def update_options(self):
        options = self.consumer.options()
        #
        # Get&Update settings
        #
        self.engine.update_options(options)
        self._options = options

        if not self._search_done:
            return

        #self._max_pages = self._options.get('count') or Config['DEFAULT'].getint('default_count')
        #
        # Change bottom progress count
        #
        #if self._max != self._max_pages:
        #    self._max = self._max_pages
        #    self._progress['bottom'][1] = self._max
        #    self._ready = False

    def _set_query(self, name, address):
        if address:
            words = re.sub(r'[\+\:\;]', '', re.sub(r'[\.\,]', ' ', address)).split() # \-
            exc = list(_const_query_exc_words)
            for word in words:
                if word.isdigit():
                    continue
                if len(word) > _const_min_word_len:
                    pass
                    #for x in words:
                    #    if word != x and word in x:
                    #        exc.append(x)
                    #        break
                else:
                    exc.append(word)
            words = ['%s+%s' % (x.isdigit() and len(x) > 5 and '!!' or '', x) for x in words if x and x not in exc]
        else:
            words = []
        if name:
            keys = name.split()
            self._query = '%s::%s !+контакт' % ( \
                ' '.join(keys[1:]),
                '!+%s %s' % (keys[0], ' '.join(['%s%s' % (len(x) > 5 and '!' or '', x) for x in words]).strip())
            )

    def _stage_0(self):
        # -------------------------
        # Run stage 0 (check state)
        # -------------------------
        if IsDeepDebug:
            self.logger.out('stage 0')

        self.engine._init_state(logger=self.logger)
        self.update_options()

        if IsSelfTest:
            # ----
            # TEST
            # ----
            if not self._total_items:
                self._total_items = len(_test_queries)

        else:
            # ----------
            # PRODUCTION
            # ----------
            if not self._total_items:
                self._total_items = self.consumer.items(mode='len')

        if not self._progress['top'][1]:
            self._progress['top'][1] = self._total_items

        self._max_pages = self._options.get('count') or Config['DEFAULT'].getint('default_count')

    def _stage_1(self):
        # --------------------------
        # Run stage 1 (top progress)
        # --------------------------
        time.sleep(self._timeout)

        n = self._progress['top'][0]

        if (not IsSelfTest and not self.consumer.items(mode='len')) or (IsSelfTest and n > len(_test_queries)-1):
            self.consumer.finish()
            return

        if IsDeepDebug:
            self.logger.out('stage 1')

        self.update_options()
        self._search_done = False

        if IsSelfTest:
            # ----
            # TEST
            # ----
            test = dict(zip('links:ob:max_pages:threshold:id'.split(':'), _test_queries[n]))

            self._id = test['id']
            ob = test['ob']

            self._company = ob[0]

            name = ob[0]
            address = ob[1]

            self._links = test['links']

            self.engine.set_links(self._links, threshold=test['threshold'])
            self._max_pages = test['max_pages'] or len(self._links)

        else:
            # ----------
            # PRODUCTION
            # ----------
            self._id = self.consumer.pop()
            ob = self.db.getParticipantById(self.db.get_ids(self._id)['pid'])

            if ob is None:
                return

            self._company = ob.Name
        
            name = ob.Name
            address = ob.Address
        
        self._set_query(name, address)
    
        self._max = len(SEARCH_ENGINES)
        self._progress['top'][2] = 'Опрос поисковых серверов...'

        if IsDeepDebug:
            self.logger.out('query[%s]' % self._query)

        # ----------------------
        # Set SearchEngine query
        # ----------------------

        self.engine.set_query(self._query)

        self._progress['bottom'][1] = self._max
        self._page = 0

    def _stage_2(self):
        # -----------------------------
        # Run stage 2 (bottom progress)
        # -----------------------------
        time.sleep(0.1)

        if IsDeepDebug:
            self.logger.out('stage 2')

        self.update_options()

        try:
            if not self._search_done:
                self.search()
            else:
                self.explore()
        except:
            print_exception()

    def init(self):
        #
        # Init next (regular) step
        #
        super().init()

        if self._progress['top'][1]:
            self._ready = True
        else:
            self._stage_0()

    def progress(self):
        self.consumer.progress()

    def top_progress(self):
        self._progress['top'][2] = '%s' % (self._company)
        self.progress()

    def bottom_progress(self):
        if not self._search_done:
            return

        self.engine.next()
        #
        # State of engine (tuple):
        #   0: current link number
        #   1: total links
        #   2: URI
        #   3: level
        #
        state = self.engine.current_state()
        
        if not state:
            return

        self._progress['bottom'][2] = state[2]
        self.progress()

    def run(self):
        #
        # Main process controller
        #
        if self._stage == 0:
            if not self._progress['top'][1] or self._progress['top'][0] < self._progress['top'][1]:
                self.top_progress()

                self._stage_1()

                self._count = 0
                self._stage = 1
            else:
                self.consumer.finish()
                self.consumer = None
                self._stage = 0
        else:
            if self._count < self._max:
                if self.consumer.getStop():
                    return
                self.bottom_progress()

                self._stage_2()

                self._progress['bottom'][0] += 1
                self._count += 1
            else:
                self._progress['top'][0] += 1
                self._stage = 0

    def unregister(self):
        #
        # Unregister *output* data in DB
        #
        if not self._id:
            return

        if IsDebug:
            self.logger.out('unregister [%s]' % self._id)

        self.db.unregister(self._id)

    def register(self, output):
        #
        # Register *output* data in DB
        #
        if output is None or not self._id:
            return

        self.unregister()

        if IsDebug:
            self.logger.out('register [%s]' % self._id)

        found = self.db.register('output', output, id=self._id)

        self._progress['found'] += found

    def search_progress(self, count, title):
        self._progress['bottom'][0] = count
        self._progress['bottom'][2] = title
        self.progress()

    def search(self):
        # ------------------------
        # Опрос поисковых сервисов
        # ------------------------
        engine = self.engine.brand(self._page)

        if IsDeepDebug:
            self.logger.out('search engine %s' % engine)

        if not self._links:
            self.search_progress(self._page, engine)
            self.engine.iter(self._page)

        self.progress()

        self._page += 1

        if self._page < len(SEARCH_ENGINES):
            return

        self.engine.begin(count=self._max_pages, unique=True)

        self._max = self._max_pages
        self._progress['top'][2] = self._company
        self._progress['bottom'] = [-1, self._max_pages, '']
        self._count = -1

        self._search_done = True
        self._ready = False

    def explore(self):
        # ----------------
        # Просмотр страниц
        # ----------------
        time.sleep(0.1)

        if IsDeepDebug:
            self.logger.out('explore page %s' % self._count)

        self.engine.go()
        count = self.engine.get_current()

        if not self.engine.is_break() and count < self._max_pages:
            self._progress['bottom'][0] = self._count = count - 1
            return

        if IsDeepDebug:
            self.logger.out('finish page %s' % count)

        self._progress['top'][1] = 0
        self._count = self._max
        self._ready = False

        self.register(self.engine.finish())
