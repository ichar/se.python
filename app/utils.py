# -*- coding: utf-8 -*-

import os
import sys
import datetime
import codecs
import math
import pytz
import re

if sys.version_info[0] > 2:
    from http.cookiejar import LWPCookieJar, Cookie
    from urllib.parse import unquote, urlparse
else:
    from cookielib import LWPCookieJar, Cookie
    from urllib import unquote
    from urlparse import urlparse

from config import (
     Config, LOCAL_TZ, IsDebug, IsDeepDebug, 
     ADDRESS_KEYS, MANAGER_KEYS, FIO_KEYS, UNUSED_EMAILS,
     BLOCK_TYPES, BLOCK_URLS, BLOCK_DOMAINS)

from .logger import Logger, default_unicode, default_encoding, default_print_encoding

empty_value = '...'

MAX_TITLE_WORD_LEN = 20

remail  = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9]+)\??")
rdomain = re.compile(r'^(http[s]?://[a-zA-Z0-9_.+-]+/)')
mdomain = re.compile(r'^(\w+@([a-zA-Z0-9_.+-]+))')
rfphone = re.compile(r"(([+\d]*?)\s*\(?(\d{3})\)?[\s\.-]*?(\d{3}\s*)[\s\.-]*?\s*(\d{2})\s*[\s\.-]*?\s*(\d{2}))", re.S)
rphone  = re.compile(r"([+\d]*?\s*\(?\d{3}\)?[\s\.-]*?\d{3}[\s\.-]*?\s*\d{2}\s*[\s\.-]*?\s*\d{2})", re.S)
rihigh  = re.compile(r'[\_\-\—\+\'\"\.\,\?\:\<\>\d\|\[\]\{\}\(\)\/\\]')
rilow   = re.compile(r'[\_\+\?\:\<\>\|\[\]\{\}\(\)\/\\]')

_global_address_rating = Config['GLOBAL'].getint('address_rating')
_global_manager_rating = Config['GLOBAL'].getint('manager_rating')

_fkeys = FIO_KEYS['F'].split(':')
_okeys = FIO_KEYS['O'].split(':')


def capitalize(s):
    out = ''
    for w in s.split():
        out += '%s%s ' % (w[0].upper(), w[1:])
    return out.strip()

def uncapitalize(s):
    return (s and len(s) > 1 and s[0].lower() + s[1:]) or (len(s) == 1 and s.lower()) or ''

def getTime():
    return datetime.datetime.now().strftime(Config['DEFAULT'].get('FULL_TIMESTAMP'))

def spent_time(start, finish=None):
    if not finish:
        finish = datetime.datetime.now()
    t = finish - start
    return (t.seconds*1000000+t.microseconds)/1000000

def mkdir(name):
    try:
        os.mkdir(name)
    except: # FileExistsError
        pass

def is_num(v):
    return re.sub('[-+\.e]?(?si)', '', v).isdigit()

def out(x):
    return x.encode(default_print_encoding, 'ignore')

def cid(ob):
    return ob and ob.id is not None and str(ob.id) or empty_value

def cdate(date, fmt=None):
    if fmt is None:
        fmt = Config['DEFAULT'].get('FULL_TIMESTAMP')
    if date and date is not None:
        try:
            x = date.replace(tzinfo=pytz.utc).astimezone(LOCAL_TZ)
        except:
            if IsDebug:
                print('>>> Invalid date: [%s]' % date)
            raise
        return str(x.strftime(fmt))
    return empty_value

def cstr(value, no_exc=None):
    try:
        return value.encode(default_unicode).decode(default_unicode)
    except:
        if not no_exc:
            raise
    return value

def clean(value):
    #print isinstance(value, unicode)
    #return value and re.sub(r'[\n\'\"\;\%\*]', '', value.encode(default_unicode, 'ignore')).strip() or ''
    #if not isinstance(value, unicode):
    #    value = value.decode(default_unicode, 'ignore')
    #value = value and value.encode(default_unicode).decode(default_unicode, 'ignore')
    return value and re.sub(r'[\n\'\"\;\%\*]', '', value).strip() or ''

def sclean(value):
    return value and \
        re.sub(r'[ ]+', ' ', 
        re.sub(r'\n\s+', '\n', 
        re.sub(r'<.*?>', '', value
    ))).strip() or ''

def cleanHtml(value):
    return value and re.sub(r'\s+', ' ', re.sub(r'<.*?>', '', value)) or ''

def get_domain(url, level=None):
    m = rdomain.search(url)
    x = m and m.group(1)
    if x and level:
        x = re.sub(r'\/', '', x)
        x = '.'.join(x.split('.')[-level:])
    return x or ''

def get_email_domain(email):
    m = mdomain.search(email.split('?')[0])
    return m and m.group(2) or ''

def get_emails(value):
    values = []
    if value:
        x = unquote(value).strip()
        m = remail.search(x)
        while m is not None:
            v = m.group(1)
            if not v in values:
                values.append(v)
            m = remail.search(x, m.end())
    return values

def get_formatted_email(value):
    m = remail.search(value)
    return m is not None and m.group(1) or ''

def get_phones(value):
    values = []
    for v in xsplit(value, ',;'):
        m = rphone.search(str(v))
        v = m is not None and re.sub(r'[\s-]', '', m.group(1)) or ''
        if not v:
            continue
        if len(re.sub(r'\D', '', v)) > 11 or not ('(' in v and ')' in v):
            continue
        if not v in values:
           values.append(v)
    return values

def get_formatted_phone(value):
    m = rfphone.search(value)
    if m is not None:
        return '+7 (%s) %s-%s-%s' % m.groups()[2:]
    else:
        return value

def get_address(value):
    return \
        re.sub(r'[\n\r]', ' ', 
        re.sub(r'[\s]+', ' ', 
        re.sub(r'<.*?>', '', 
            value
        )))

def get_fio(value):
    words = list(filter(lambda x: not is_num(x), value.split()))
    if len(words) < 3:
        return ''
    v = value.strip().lower()
    mkey = ''
    ex = 0
    for w, key in MANAGER_KEYS:
        if key in v:
            ex = len(key.split())
            mkey = key
            break
    if is_valid_fio(value) or (ex and len(words) == ex+3 and mkey in v):
        if min([len(x) for x in words]) > 3:
            return value
    return ''

def get_manager(value):
    v = \
        re.sub(r'[\n\r]', ' ', 
        re.sub(r'[\s]+', ' ', 
        re.sub(r'<.*?>', '', 
            value
        ))).strip().lower()
    p = ''
    for rating, key in MANAGER_KEYS:
        if key in v:
            p = capitalize(key)
            break
    return p

def is_key_inside(value, keys, ends_with=None):
    ex = False
    if value and keys:
        for x in keys:
            if x != value:
                if ends_with:
                    if value.endswith(x):
                        ex = True
                else:
                    if x in value:
                        ex = True
                if ex:
                    break
    return ex

def is_value_inside(value, keys, ends_with=None):
    ex = False
    if value and keys:
        for x in keys:
            if x != value:
                if ends_with:
                    if value.endswith(x):
                        ex = True
                else:
                    if value in x:
                        ex = True
                if ex:
                    break
    return ex

def is_valid_info(value, low=False):
    if not value:
        return False
    if low:
        return rilow.search(value) is None
    else:
        return rihigh.search(value) is None

def is_valid_alias(value):
    return len(value) <= 250 and True or False

def is_valid_href(href):
    if not href:
        return False
    if not href.startswith('http'):
        return False
    
    if len(href.split('?')) > 2:
        return False
    
    href = unquote(href).lower()
    
    for x in BLOCK_TYPES:
        if href.endswith(x):
            return False
    for x in BLOCK_DOMAINS:
        if x in get_domain(href):
            return False
    for x in BLOCK_URLS:
        if x in href:
            return False

    o = urlparse(href, 'http')
    if x in ['redirect', get_domain(href)]:
        if x in o.query:
            return False

    uri = href.replace('https://', '').replace('http://', '')
    for x in uri.split('/'):
        if ':' in x:
            return False
    
    return True

def is_valid_phone(value):
    if value:
        m = rphone.search(value)
        v = m and m.group(1)
    else:
        v = ''
    return v and v in value and True or False

def is_valid_email(value):
    m = remail.search(value)
    v = m and m.group(1)
    if v and not is_key_inside(v, '%^*='):
        for x in UNUSED_EMAILS:
            if x in v:
                v = None
                break
    else:
        v = None
    return v and v in value and True or False

def is_valid_address(value, query=None):
    if not is_valid_info(value, low=True):
        return False
    v = value.lower()
    r = 0
    for rating, key in ADDRESS_KEYS:
        if key in v:
            r += rating
    if query and query in v:
        r += 5
    return r > _global_address_rating and True or False

def is_valid_manager(value, query=None):
    if not is_valid_info(value, low=True):
        return False
    v = value.strip().lower()
    r = 0
    for rating, key in MANAGER_KEYS:
        if key in v:
            r += rating
    if query and query in v:
        r += 5
    return r > _global_manager_rating and True or False

def is_valid_fio(value):
    if not value:
        return False
    v = value.strip().lower().split()
    return len(v) == 3 and ( \
        is_key_inside(v[0], _fkeys, ends_with=True) and \
        is_key_inside(v[2], _okeys, ends_with=True) and \
        capitalize(value) == value
    ) and True or False

def xsplit(value, keys):
    out = [value]
    for s in keys:
        l = range(len(out))
        for n in l:
            v = out.pop(0)
            out += [x.strip() for x in v.split(s)]
    return list(set(out))

def usplitter(values, keys):
    items = []
    for x in values:
        items += xsplit(x, keys)
    return list(set(items))

def splitter(value, length=None, comma=','):
    if value and len(value) > (length or MAX_TITLE_WORD_LEN):
        changed, v = worder(value, length=length, comma=comma in value and comma)
        return v
    return value

def worder(value, length=None, comma=None):
    max_len = (not length or length < 0) and MAX_TITLE_WORD_LEN or length
    words = value.split()
    s = ''
    changed = 0
    while len(words):
        word = words.pop(0).strip()
        if s:
            s += ' '
        if len(word) <= max_len:
            s += word
        else:
            w = word[max_len:]
            if comma and comma in w:
                words = ['%s%s%s' % (x.strip(), comma, ' ') for x in w.split(comma)] + words
            else:
                words.insert(0, w)
            s += word[:max_len]
            changed = 1
    s = s.strip()
    if comma and s.endswith(comma):
        s = s[:-1]
    return changed, s

def make_cookiejar_from_dict(values, cookies=None):
    #
    # http://stackoverflow.com/questions/6878418/putting-a-cookie-in-a-cookiejar
    #
    #{'name': 'ASP.NET_SessionId', 'value': 'sude5zxuudcfk3d5t203wqwc', 'httpOnly': True, 'path': '/', 'secure': False, 'domain': 'kad.arbitr.ru'}
    #{'name': '__utmc', 'value': '228081543', 'httpOnly': False, 'path': '/', 'secure': False, 'domain': '.kad.arbitr.ru'}
    #{'name': 'CUID', 'value': '576d233c-bc65-4430-b5c1-a39e94d0d3b2:f6sNpWbaQTdmtucK4CSCzQ==', 'expiry': 1759963880.830987, 'httpOnly': True, 'path': '/', 'secure': False, 'domain': '.arbitr.ru'}
    #{'name': '__utmt', 'value': '1', 'expiry': 1444345280, 'httpOnly': False, 'path': '/', 'secure': False, 'domain': '.kad.arbitr.ru'}
    #{'name': '__utma', 'value': '228081543.379602695.1444344680.1444344680.1444344680.1', 'expiry': 1507416680, 'httpOnly': False, 'path': '/', 'secure': False, 'domain': '.kad.arbitr.ru'}
    #{'name': '__utmz', 'value': '228081543.1444344680.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none)', 'expiry': 1460112680, 'httpOnly': False, 'path': '/', 'secure': False, 'domain': '.kad.arbitr.ru'}
    #{'name': '__utmb', 'value': '228081543.1.10.1444344680', 'expiry': 1444346480, 'httpOnly': False, 'path': '/', 'secure': False, 'domain': '.kad.arbitr.ru'}

    if cookies is None:
        cookies = LWPCookieJar() #requests.cookies.RequestsCookieJar()

    for x in values:
        version = x.get('version') or 0
        name = x.get('name')
        value = x.get('value')

        port = None # '80'
        port_specified = False

        domain = x.get('domain')
        domain_specified = True
        domain_initial_dot = domain.startswith('.')
        
        path = x.get('path')
        path_specified = path and True or False

        #httpOnly = x.get('httpOnly')
        #if httponly == '':
        #    if 'httponly' in headers['set-cookie'].lower():
        #        httponly = True
        #else:
        #    httponly = False

        secure = x.get('secure')
        expires = None #x.get('expires')
        discard = True

        #ValueError: invalid literal for int() with base 10: 'Сб, 09 апр 2016 13:02:11 GMT'
        #if type(expires) == str:
        #    tmp = time_to_tuple(expires)
        #    expires = timeto(tmp[0], tmp[1], tmp[2], tmp[3], tmp[4], tmp[5])
        
        comment = x.get('comment')
        comment_url = None
        rest = {}

        if 'HttpOnly' in x:
            rest['HttpOnly'] = x.get('httpOnly')
        if 'expiry' in x:
            rest['expiry'] = x.get('expiry')
        if 'max_age' in x:
            rets['max_age'] = x.get('max-age')

        cookie = Cookie(
                 version, name, value,
                 port, port_specified,
                 domain, domain_specified, domain_initial_dot,
                 path, path_specified,
                 secure,
                 expires,
                 discard,
                 comment,
                 comment_url,
                 rest,
                 rfc2109=False
        )
        cookies.set_cookie(cookie)

    return cookies

def make_html(output):
    html = output.replace('.txt', '.html')
    so = Logger(html, default_unicode, 'w', bom=True)

    so.out('<html><head>')
    so.out(""" \
        <style type="text/css">
            body { font:normal 12px Tahoma; }
            span.mode { color:green; font-weight:bold; }
        </style>
    """)
    so.out('</head><body>')

    with open(output, mode='r', encoding=default_unicode) as fin: #
        for line in iter(fin.readline, ''):
            line = re.sub(r'(^http.*$)', r'<a href="\1" target="_blank">\1</a>', line)
            line = re.sub(r'(email|phone|address|manager):', r'<span class="mode">\1:</span>', line)
            line = re.sub(r'\n', '<br>\n', line)
            so.out(line)

    so.out('</body></html>')

    so.close()
    del so

def get_upload_dumps(tmp):
    giud = re.compile(r'(\d{14,}?)(-)?(\w{8,}?-\w{4,}?-\w{4,}?-\w{4,}?-\w{12,}?)?')

    dumps = []
    case = ''
    documents = []

    for name in sorted(os.listdir(tmp)):
        p = os.path.join(tmp, name)

        if os.path.isfile(p):
            m = re.search(giud, name.split('.')[0])
            if m is not None:
                c, s, d = m.groups()
                if c and s and d:
                    if not d in documents:
                        documents.append(d)
                elif c and c != case:
                    case = c
                    if case and documents:
                        dumps.append((case, documents,))
                    documents = []

    if case and documents:
        dumps.append((case, documents,))

    return dumps

def round_up(value):
    return math.ceil(value)
