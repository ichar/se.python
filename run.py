#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re
import datetime
import traceback

from optparse import OptionParser, OptionGroup, IndentedHelpFormatter

from config import Config
from app.logger import Logger, setup_console, log, EOR, EOL
from app.core import SearchEngine #, Cookies, Page, is_valid_href, is_valid_alias, parser_get_alias, parser_unquote, spent_time
from app.utils import spent_time

basedir = os.path.abspath(os.path.dirname(__file__))
errorlog = None

IsDebug = 0         # debug/dump
IsDeepDebug = 0     # for google test only
IsTrace = 0         # show progress
IsTest = 0          # self test without SE

default_language    = Config['DEFAULT'].get     ('default_language')
default_timeout     = Config['DEFAULT'].getfloat('default_timeout')
default_pause       = Config['DEFAULT'].getfloat('default_pause')
default_count       = Config['DEFAULT'].getint  ('default_count')
default_depth       = Config['DEFAULT'].getint  ('default_depth')
default_threshold   = Config['DEFAULT'].getint  ('default_threshold')
default_stop        = Config['DEFAULT'].getint  ('default_stop')
default_engines     = Config['DEFAULT'].get     ('default_engines')


_test_urls = (                                                   # тестовый запрос (query):
    #(1, 'http://catalog.metalika.su/metal-firm/skalins'),       # метал
    #(1, 'http://www.yell.ru/moscow/com/avtolider_1929804/'),    # автолидер|авто
    #(1, 'http://www.samsung.com/ru/home/'),                     # самсунг
    #(1, 'http://skalins.ru/'),                                  # скалинс
    (1, 'http://www.skalins.ru/index.php?option=com_content&view=article&id=6'),
)

_options = ( \
    ['-', 'E', {'action':'store_true', 'default':True, 'dest':'email', 'help':'scrape email addresses (default)'}],
    ['-', 'e', {'action':'store_false', 'dest':'email', 'help':"don't scrape email addresses"}],
    ['-', 'P', {'action':'store_true', 'default':True, 'dest':'phone', 'help':'scrape phone number (default)'}],
    ['-', 'p', {'action':'store_false', 'dest':'phone', 'help':"don't scrape phone number"}],
    ['-', 'A', {'action':'store_true', 'default':True, 'dest':'address', 'help':'scrape address (default)'}],
    ['-', 'a', {'action':'store_false', 'dest':'address', 'help':"don't scrape address"}],
    ['-', 'M', {'action':'store_true', 'default':True, 'dest':'manager', 'help':'scrape manager (default)'}],
    ['-', 'm', {'action':'store_false', 'dest':'manager', 'help':"don't scrape manager"}],
    ['-', 'S', {'action':'store_true', 'default':True, 'dest':'string', 'help':"parse tag's string content (default)"}],
    ['-', 's', {'action':'store_false', 'dest':'string', 'help':"don't parse tag's string content"}],
    ['-', 'U', {'action':'store_true', 'default':True, 'dest':'unique', 'help':"output unique results only (default)"}],
    ['-', 'u', {'action':'store_false', 'dest':'unique', 'help':"output all found results"}],
    ['-', 'X', {'action':'store_true', 'default':True, 'dest':'top', 'help':"output *top* results only (default)"}],
    ['-', 'x', {'action':'store_false', 'dest':'top', 'help':"output all found results"}],

    ['--', 'language',  {'metavar':default_language, 'type':'string', 'default':default_language, 'help':'produce results in the given language'}],
    ['--', 'timeout',   {'metavar':default_timeout, 'type':'float', 'default':default_timeout, 'help':'timeout to wait response in seconds'}],
    ['--', 'pause',     {'metavar':default_pause, 'type':'float', 'default':default_pause, 'help':'pause between HTTP requests in seconds'}],
    ['--', 'count',     {'metavar':default_count, 'type':'int', 'default':default_count, 'help':'count of web-sources walking'}],
    ['--', 'depth',     {'metavar':default_depth, 'type':'int', 'default':default_depth, 'help':'depth of links'}],
    ['--', 'threshold', {'metavar':default_threshold, 'type':'int', 'default':default_threshold, 'help':'threshold for rating of a page'}],
    ['--', 'engines',   {'metavar':default_engines, 'type':'string', 'default':default_engines, 'help':'search engines: ABGHMRY, Ask|Bing|Google|yaHoo|Mail|Rambler|Yandex'}],
    ['--', 'stop',      {'metavar':default_stop, 'type':'int', 'default':default_stop, 'help':'max count of search responses'}],
)

_debug_options = ( \
    ['-d', '--debug', {'action':'store_true', 'default':IsDebug and True or False, 'help':"debug script"}],
    ['-D', '--deepdebug', {'action':'store_true', 'default':IsDeepDebug and True or False, 'help':"debug google response"}],
    ['-t', '--trace', {'action':'store_true', 'default':IsTrace and True or False, 'help':"show trace"}],
    ['-T', '--test', {'action':'store_true', 'default':IsTest and True or False, 'help':"self test"}],
)

logger = None
links = []


class HelpFormatter(IndentedHelpFormatter):

    def __init__(self, banner, info, *argv, **argd):
        self.banner = banner
        self.info = info
        IndentedHelpFormatter.__init__(self, *argv, **argd)

    def format_usage(self, usage):
        msg = IndentedHelpFormatter.format_usage(self, usage)
        return '%s\n%s\n%s\n' % (self.banner, msg, self.info)


if __name__ == "__main__":
    logger = Logger(False)

    setup_console()
    errorlog = open(Config['RUNTIME'].get('errorlog'), 'a') #os.path.join(basedir, 'traceback.log')

    formatter = HelpFormatter(
        "Python script to scrape simple HTML content by a given query.\n",
        "Query format: <mandatory>[::<optional google keywords>]\n\n"
        "Look at Google like:\n\n"
        "  http://www.diacr.ru/zametki/20-kak-pravilno-iskat-v-google/kak-pravilno-iskat-v-google.htm"
    )

    parser = OptionParser(formatter=formatter)
    parser.set_usage(
        "%prog [options] query"
    )

    for op in _options:
        parser.add_option('%s%s' % (op[0], op[1]), **op[2])

    debug_options = OptionGroup(parser, "Debug Options")
    for op in _debug_options:
        debug_options.add_option(op[0], op[1], **op[2])
    parser.add_option_group(debug_options)

    options, args = parser.parse_args()
    query = ' '.join(args)
    if not query:
        parser.print_help()
        sys.exit(2)

    params = [(k, v) for (k, v) in options.__dict__.items() if not k.startswith('_')]
    params = dict(params)

    IsDebug = not IsDebug and options.debug and 1 or 0
    IsDeepDebug = not IsDeepDebug and options.deepdebug and 1 or 0
    IsTrace = not IsTrace and options.trace and 1 or 0
    IsTest = not IsTest and options.test and 1 or 0

    logger.out('query[%s]' % (query))
    logger.out('options[{%s}]' % ', '.join(["'%s': %s" % (x, str(params.get(x))) for x in sorted(params)]))

    start = datetime.datetime.now()
    ask_links = bing_links = google_links = mail_links = rambler_links = yahoo_links = yandex_links = 0

    engine = SearchEngine(options.engines, params, language=options.language, errorlog=errorlog)
    engine._init_state(logger=logger)

    if not IsTest:
        if IsDeepDebug:
            logger.out('Search query:[%s]' % query)

        links = engine.search(query)

        ask_links, bing_links, google_links, mail_links, rambler_links, yahoo_links, yandex_links = \
            engine.state()

        #if IsDebug:
        #    log(os.path.join(basedir, 'links.log'), [x[1] for x in links], mode='a+b', bom=False)
    else:
        engine.set_query(query)

        links = [x for x in _test_urls]
        engine.set_links(links)

    logger.out('')

    if not IsDeepDebug and len(links):
        total_links = engine.explore(**params)
    else:
        total_links = ask_links + bing_links + google_links + mail_links + rambler_links + yahoo_links + yandex_links

    logger.out('Ask response:[%s]' % ask_links)
    logger.out('Bing response:[%s]' % bing_links)
    logger.out('Google response:[%s]' % google_links)
    logger.out('Mail response:[%s]' % mail_links)
    logger.out('Rambler response:[%s]' % rambler_links)
    logger.out('Yahoo response:[%s]' % yahoo_links)
    logger.out('Yandex response:[%s]' % yandex_links)
    logger.out('Total links:[%s]' % total_links)

    finish = datetime.datetime.now()
    t = finish - start
    logger.out('Started at %s' % start.strftime(Config['DEFAULT'].get('SPENT_TIMESTAMP')))
    logger.out('Finished at %s' % finish.strftime(Config['DEFAULT'].get('SPENT_TIMESTAMP')))
    logger.out('Spent time: %s sec' % spent_time(start, finish))

    errorlog.close()
    logger.close()
