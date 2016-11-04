# -*- coding: utf-8 -*-

import os
import sys
import time
import random
import datetime
import re

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(basedir)

if sys.version_info[0] > 2:
    from bs4 import BeautifulSoup, Tag, NavigableString, Comment
    from http.cookiejar import LWPCookieJar, Cookie
    from urllib.request import Request, urlopen
    from urllib.parse import quote_plus, urlparse, parse_qs, unquote
    from urllib.error import HTTPError
else:
    from BeautifulSoup import BeautifulSoup, Tag, NavigableString, Comment
    from cookielib import LWPCookieJar, Cookie
    from urllib import quote_plus, unquote
    from urllib2 import Request, urlopen, HTTPError
    from urlparse import urlparse, parse_qs

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException

import json
import requests

from config import (
     Config, 
     ADDRESS_KEYS, MANAGER_KEYS, BLOCK_DOMAINS, BLOCK_TYPES, UNUSED_TAGS, UNUSED_EMAILS, TAG_RATING,
     KAD_SERVICES, KAD_CASE_KEYS, KAD_PARTICIPANT_KEYS)

from app.logger import Logger, default_unicode, setup_console, log, dump, conv_rus_eng, EOR, EOL
from app.core import get_page_agent, parser_add_href
from app.models import Case, Plaintiff, Respondent, Participant, Email, Phone, Manager
#from app.models import create_db
from app.dbase import DBConnector
from app.utils import get_domain, get_emails, get_phones, is_key_inside, make_cookiejar_from_dict

#from run import links, get_query, explore
from app.services import BaseProxy


def create_db():
    db = DBConnector(echo=True, debug=True)
    db.create_database()
    db.close()
    #create_db()

def test_kad_dbload(dump, count=10, forced=False):
    with open(os.path.join(basedir, Config['OUTPUT'].get('tmp_folder'), dump)) as si:
        data = json.load(si)

    db = DBConnector(echo=False, debug=True)
    session = db.open_session()

    key = ['Г', 'Г:АС города Москвы']

    n = 0
    for item in data['Result']['Items']:
        if count and n >= count:
            break
        if not forced:
            #if key[1] != ('%s:%s' % (item['CaseType'], item['CourtName'])):
            #    continue
            if key[0] != ('%s' % item['CaseType']):
                continue

        case = Case('MSK', 'G', columns=item)
        db.add(case)

        for i, subitem in enumerate(item['Plaintiffs']['Participants']):
            if i >= item['Plaintiffs']['Count']:
                break

            participant = Participant(subitem)
            db.add(participant)

            plaintiff = Plaintiff(case, participant)
            db.add(plaintiff)

        for i, subitem in enumerate(item['Respondents']['Participants']):
            if i >= item['Respondents']['Count']:
                break

            participant = Participant(subitem)
            db.add(participant)

            respondent = Respondent(case, participant)
            db.add(respondent)

        n += 1

    db.commit()

    out = db.session.query(Case).order_by(Case.CaseId).all()
    
    for n, ob in enumerate(out):
        print('%03d %s' % (n, ob))

    db.close_session()

    return len(out), data

def test_kad_documents(document_id):
    #
    # http://kad.arbitr.ru/Kad/InstanceDocumentsPage?_=1444054500881&id=eff41d24-d2e2-4a01-be85-0a182d8165eb&withProtocols=true&perPage=30&page=1
    #   document_id (id): eff41d24-d2e2-4a01-be85-0a182d8165eb
    # json.dump(out, open('tmp/out.documents.dump', 'w'), indent=2)
    #
    base_url = 'http://kad.arbitr.ru/'

    url = base_url

    response = requests.get(url)
    
    if response is None or response.status_code != 200:
        return response and response.status_code or 'Error-1'

    cookies = response.cookies

    h = {}
    h['User-Agent']='Mozilla/5.0 (Windows NT 6.0; rv:40.0) Gecko/20100101 Firefox/40.0'
    h['Accept']='application/json, text/javascript, */*'
    h['Accept-Language']='ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3'
    h['Accept-Encoding']='gzip, deflate'
    h['Content-Type']='application/json'
    h['X-Requested-With']='XMLHttpRequest'
    #h['x-date-format']='iso'
    h['Referer']='%sKad/Card' % base_url
    #h['Content-Length']=128
    h['Connection']='keep-alive'
    #h['Pragma']='no-cache'
    #h['Cache-Control']='max-age=0'

    headers = h.copy()

    print(url)

    save_cookies = """
        CUID=fffb9ef5-e6b9-4790-9f38-5d63469196ba:iFOArBWLqgaTpqr9rpKc5A==; 
        __utma=228081543.340151020.1443131032.1444042324.1444044971.8; 
        __utmz=228081543.1443131032.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none); 
        KadLVCards=%d0%9040-186234%2f2015~%d0%9040-86579%2f2010~%d0%9040-178400%2f2015~%d0%9040-179790%2f2015~%d0%9040-180339%2f2015; 
        ASP.NET_SessionId=ksariiqmfbdesai0jsfulzrk; __utmc=228081543; __utmb=228081543.9.10.1444044971; __utmt=1
    """

    time.sleep(3.0)

    url = base_url + KAD_SERVICES['getInstanceDocumentsPage'] + '?id=' + document_id + '&withProtocols=true&perPage=30&page=1'

    response = requests.get(url, headers=headers, cookies=cookies)

    print(url)
    
    if response is None or response.status_code != 200:
        return response and response.status_code or 'Error-2'

    out = json.loads(response.text)

    if not out:
        return 'no results'

    res = out['Result']

    for n, item in enumerate(res['Items']):
        print('%03d [%s] %s' % (n+1, item['ClaimSum'], item['AdditionalInfo']))
        print('... %s %s' % (item['CourtTag'], item['CourtName']))
        print('... %s Started: [%s]' % (item['DisplayDate'], item['IsStart'] and 'Y' or 'N'))

        for x in item['Declarers']:
            print('... %s, %s' % (x['Organization'], x['Address']))

    return res['TotalCount'], out

def test_kad_card(case_id):
    #
    # http://kad.arbitr.ru/Card/798decb3-2c17-4e30-9247-36c284c66bf4
    #   case_id: 798decb3-2c17-4e30-9247-36c284c66bf4
    # out: html
    # tag: <input class="js-instanceId" value="f00a1954-f3d7-47ef-91b5-2dca244f7088" type="hidden">
    #   document_id (value): f00a1954-f3d7-47ef-91b5-2dca244f7088
    #
    base_url = 'http://kad.arbitr.ru/'

    url = base_url

    response = requests.get(url)
    
    if response is None or response.status_code != 200:
        return response and response.status_code or 'Error-1'

    cookies = response.cookies

    h = {}
    h['User-Agent']='Mozilla/5.0 (Windows NT 6.0; rv:40.0) Gecko/20100101 Firefox/40.0'
    h['Accept']='text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    h['Accept-Language']='ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3'
    h['Accept-Encoding']='gzip, deflate'
    #h['Content-Type']='application/json; charset=UTF-8'
    #h['X-Requested-With']='XMLHttpRequest'
    #h['x-date-format']='iso'
    h['Referer']=base_url
    #h['Content-Length']=128
    h['Connection']='keep-alive'
    #h['Pragma']='no-cache'
    h['Cache-Control']='max-age=0'

    headers = h.copy()

    print(url)

    save_cookies = """
        CUID=fffb9ef5-e6b9-4790-9f38-5d63469196ba:iFOArBWLqgaTpqr9rpKc5A==; 
        __utma=228081543.340151020.1443131032.1443997500.1444042324.7; 
        __utmz=228081543.1443131032.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none); 
        KadLVCards=%d0%9040-186234%2f2015~%d0%9040-86579%2f2010~%d0%9040-178400%2f2015~%d0%9040-179790%2f2015~%d0%9040-180339%2f2015; 
        ASP.NET_SessionId=ksariiqmfbdesai0jsfulzrk; 
        notShowTooltip=yes; 
        __utmc=228081543; 
        __utmb=228081543.1.10.1444042324; 
        __utmt=1
    """

    time.sleep(3.0)

    url = base_url + KAD_SERVICES['getCard'] + '/' + case_id

    response = requests.get(url, headers=headers, cookies=cookies)

    print(url)
    
    if response is None or response.status_code != 200:
        return response and response.status_code or 'Error-2'

    html = response.text

    soup = BeautifulSoup(html, Config['DEFAULT'].get('default_html_parser'))
    
    tag = soup.find('input', attrs={'class':"js-instanceId"})
        
    if not tag:
        return 'Error-3'

    print('--> document_id: %s' % tag.attrs['value'])

    return html

def test_kad_search(page, count=None, case_type=None, date_from=None, json_dump=None, proxy=None, use_cookies=True, use_selenium=False):
    #
    # json.dump(out, open('tmp/out.cases.dump', 'w'), indent=2)
    #
    base_url = 'http://kad.arbitr.ru/'

    url = base_url

    h = {}

    use_proxy = proxy and True or False

    if use_proxy:
        #'http': 'http://109.163.241.49:8080'   # ( 1.871)
        #'http': 'http://46.52.164.158:9999'    # ( 4.874)
        #'http': 'http://195.239.105.218:3128'  # (12.302)
        #'http': 'http://...
        #'http': 'http://194.190.143.25:3128'
        #'http': 'http://195.239.105.218:3128'
        proxies = {'http' : 'http://%s' % proxy}
    else:
        proxies = None

    if use_selenium:
        h['User-Agent']='Mozilla/5.0 (Windows NT 6.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36'
        html, cookies = test_selenium(url, mode='html')
        cookies = make_cookiejar_from_dict(cookies)
        
    elif use_cookies:
        h['User-Agent']='Mozilla/5.0 (Windows NT 6.0; rv:40.0) Gecko/20100101 Firefox/40.0'

        try:
            response = requests.get(url, proxies=proxies)
        except:
            response = None
    
        if response is None or response.status_code != 200:
            return response and response.status_code or 'Error-1'

        cookies = response.cookies

    else:
        h['User-Agent']='Mozilla/5.0 (Windows NT 6.0; rv:40.0) Gecko/20100101 Firefox/40.0'
        cookies = None

    h['Accept']='application/json, text/javascript, */*'
    h['Accept-Language']='ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3'
    h['Accept-Encoding']='gzip, deflate'
    h['Content-Type']='application/json; charset=UTF-8'
    h['X-Requested-With']='XMLHttpRequest'
    h['x-date-format']='iso'
    h['Referer']=base_url
    h['Content-Length']=128
    h['Connection']='keep-alive'
    h['Pragma']='no-cache'
    h['Cache-Control']='no-cache'    

    headers = h.copy()

    data = {
        "Page":page or 1,
        "Count":count or 25,
        "Courts":['MSK'],
        "DateFrom":date_from,
        "DateTo":None,
        "Sides":[],
        "Judges":[],
        "CaseType":case_type or 'G',
        "CaseNumbers":[],
        "WithVKSInstances":False
    }

    save_cookies = """
        Cookie: 
        ASP.NET_SessionId=bk4cyqejlzxacoqjgvsszztd; 
        CUID=fffb9ef5-e6b9-4790-9f38-5d63469196ba:iFOArBWLqgaTpqr9rpKc5A==;
        __utma=228081543.340151020.1443131032.1443131032.1443131032.1;
        __utmb=228081543.3.10.1443131032; 
        __utmc=228081543;
        __utmz=228081543.1443131032.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none); 
        __utmt=1
    """

    time.sleep(3.0)

    url = base_url + KAD_SERVICES['getInstances']

    try:
        response = requests.get(url, json=data, headers=headers, cookies=cookies, proxies=proxies)
    except:
        response = None
    
    if response is None or response.status_code != 200:
        return response and response.status_code or 'Error-2', response, cookies

    out = json.loads(response.text)

    if not out or not 'Result' in out:
        return 'no results', response, cookies

    res = out['Result']

    total = res['TotalCount']
    pages = res['PagesCount']
    size = res['PageSize']

    start = size*(page-1)+1

    for n, item in enumerate(res['Items']):
        print('%03d %s' % (start+n, item['CaseId']))
        print('>>> %s' % item['Plaintiffs']['Participants'][0]['Name'])

        for x in item['Respondents']['Participants']:
            print('--> %s' % x['Name'])
            print('... %s' % x['Address'])
            print('... %s' % str(x.get('SubjectCategories') or ''))

        print('... %s: %s = %s (%s)' % (str(item['Date']), item['CaseNumber'], item['CourtName'], item['CaseType']))

    if json_dump:
        tmp = os.path.join(basedir, Config['OUTPUT'].get('tmp_folder'))
        dump(os.path.join(tmp, '%s.cases.txt' % json_dump), response.text)
        json.dump(out, open(os.path.join(tmp, '%s.dump' % json_dump), 'w'), indent=4)

    return total, pages, size, response, cookies

def test_request(url, headers={}):
    request = Request(url)
    request.add_header('User-Agent', get_page_agent())

    for x in headers:
        #print('--> %s:%s' % (x, headers[x]))
        request.add_header(x, headers[x])
    
    response = urlopen(request, timeout=10.0)
    
    html = response.read()
    response.close()
    
    if html:
        soup = BeautifulSoup(html, Config['DEFAULT'].get('default_html_parser'))
    else:
        soup = None
    
    return html, soup

def test_selenium(url, mode='emails', timeout=10.0, inner_html=False):
    try:
        #driver = webdriver.Chrome()
        driver = webdriver.PhantomJS()
    except WebDriverException as e:
        raise

    driver.set_window_size(600, 400)
    
    if timeout:
        driver.set_page_load_timeout(timeout or Config['DEFAULT'].get('default_timeout'))
    
    driver.get(url)

    html = ''

    if inner_html:
        try:
            html = driver.execute_script('return document.body.innerHTML;')
        except WebDriverException as e:
            pass
    if not html:
        html = driver.page_source

    cookies = driver.get_cookies()

    driver.quit()

    if mode == 'html':
        return html, cookies

    soup = BeautifulSoup(html, Config['DEFAULT'].get('default_html_parser'))

    if soup is not None:
        if mode == 'emails':
            emails = []
            for a in soup.body.findAll('a'):
                href = a.attrs.get('href')
                for email in get_emails(href):
                    emails.append(email)
            return emails
        if mode == 'links':
            links = []
            domain = get_domain(url)
            for a in soup.body.findAll('a'):
                href = a.attrs.get('href')
                if href not in links:
                    links.append(unquote(parser_add_href(domain, href)))
            return links

    return soup, cookies

def get_css(url):
    html, soup = test_request(url, headers={ \
        'Accept' : 'text/css,*/*;q=0.1',
        'Accept-Language' : 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        #'Accept-Encoding' : 'gzip, deflate',
        'Referer' : 'http://www.samair.ru/proxy/',
        'Connection' : 'keep-alive',
        'Pragma' : 'no-cache',
        #'If-Modified-Since' : 'Fri, 04 Dec 2015 13:43:02 GMT',
        #'If-None-Match' : '"3f0335-88a-52612afaa6580"',
        'Cache-Control' : 'max-age=0',
    })
    css = {}
    for x in soup.contents[0].split('\n'):
        #print(x)
        try:
            c,v = re.sub(r'after\s+{content:"([\d]+)"}', r'\1', x).split(':')
            css[c[1:]] = v
        except:
            pass
    return css

def check_proxy(proxy):
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

    if 'ip' in ipinfo and ipinfo['ip']:
        online = True
        status = 'Proxy is working.'
    else:
        status = 'Proxy check failed: %s is not used while requesting' % proxy

    print(ipinfo)

    return online

def get_proxy(url):
    #
    # Free Proxy list: http://www.samair.ru/proxy/
    #
    html, soup = test_request(url, headers={ \
        'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language' : 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Referer' : 'http://www.samair.ru/proxy/',
        'Connection' : 'keep-alive',
        'Cache-Control' : 'max-age=0',
    })
    
    if soup is None:
        return 'Error-1'

    href = ''
    for item in soup.findAll('link'):
        attrs = dict(item.attrs)
        if not ('type' in attrs and 'href' in attrs):
            continue
        if attrs['type'] != 'text/css':
            continue
        href = attrs['href']
        if not href.startswith('/styles/'):
            continue
        break

    if not href:
        return 'Error-2'

    url_css = '%s%s' % (get_domain(url)[:-1], href)
    #print(url_css)

    css = get_css(url_css)
    #print(css)

    table = soup.find('table', attrs={'id':'proxylist'})

    if not table:
        return 'Error-3'

    proxies = {}
    for tr in table.findAll('tr'):
        if tr is None or len(tr.contents) != 4:
            continue
        #print(tr.contents)
        p = ''
        for tag in tr.findAll('span'):
            if tag is None or not isinstance(tag, Tag):
                continue
            #print('tag:'+''.join(tag.contents))
            if not 'class' in tag.attrs:
                continue
            c = tag.attrs['class'][0].replace('.', '')
            if not c in css:
                continue
            #print('class:'+c)
            v = str(tag.string or '').strip()
            #print('value:'+v)
            if c and v:
                p = '%s%s' % (v, css.get(c))
                break
        proxy_type = tr.contents[1].string.strip()
        land = tr.contents[3].string
        if p and land:
            proxies[p] = {'type':proxy_type, 'land':land, 'response':0, 'online':None}

    return proxies

def test_proxy(url, pages, prefix=None, check_online=False):
    proxy = BaseProxy(url or 'http://www.samair.ru/proxy/')
    proxy(pages or 2, prefix=prefix, check_online=check_online)
    return proxy

def test_kad_search_with_proxy(page, use_cookies=True, use_selenium=False):
    p = test_proxy('http://www.samair.ru/proxy-by-country', 10, prefix='Russian-Federation', check_online=True)

    print('Total proxies: %s' % len(p._ip))

    valid_proxies = []

    while p is not None:
        proxy = p.get()
        if not proxy:
            break
        print('==> %s' % proxy)
        x = test_kad_search(page, proxy=proxy, use_cookies=use_cookies)
        if len(x) > 3:
            valid_proxies.append((proxy, p._proxies[proxy]))
            page += 1

    return valid_proxies

def get_db():
    return DBConnector()

def grc(case_id, with_log=None):
    #
    # Get Respondent by Case
    #
    return get_db().getRespondentByCase(case_id, with_log=with_log)

def gsr(with_log=None):
    #
    # Get Sorted Respondent
    #
    return get_db().getSortedRespondent(with_log=with_log)

def gcp(view='log', page=1, size=50, with_log=None, show=True):
    #
    # Get Cases Page
    #
    return get_db().getCasesPage(view, page, size, with_log=with_log, show=show)

def gci(id, show=True):
    #
    # Get Case by ID
    #
    return get_db().getCaseItem(id, show=show)

def gpi(id, show=True):
    #
    # Get Participant by ID
    #
    return get_db().getParticipantById(id, show=show)

def grci(cid, pid=None, show=True):
    #
    # Get Respondent by Case ID
    #
    return get_db().getRespondentByCaseId(cid, pid, show=show)

def ge(id=None, pid=None, show=True):
    #
    # Get Emails by Participant ID
    #
    return get_db().getEmails(id=id, pid=pid, show=show)

def gp(id=None, pid=None, show=True):
    #
    # Get Phones by Participant ID
    #
    return get_db().getPhones(id, pid, show=show)

def register_proxy(ip, response):
    data = (ip, {'kind':'default', 'land':None, 'response':response, 'online':True})
    return get_db().register('proxy', data)


if __name__ == "__main__":
    create_db()

    register_proxy('109.163.241.49:8080', 1.871)
    register_proxy('46.52.164.158:9999', 4.874)
    register_proxy('109.232.106.142:3128', 0.311)
