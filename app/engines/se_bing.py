#!/usr/bin/env python

__all__ = ['BingSearchEngine', 'search']

import os
import sys
import datetime

from ..logger import EOL, print_exception
from ..core import BaseSearchEngine
from config import Config

basedir = os.path.abspath(os.path.dirname(__file__))
errorlog = None

_section = Config['BING']

_urls = { \
    'home'          : "http://www.bing.%(tld)s/",
    'search'        : "http://www.bing.%(tld)s/search?q=%(query)s&first=%(start)d",
    'next_page'     : "http://www.bing.%(tld)s/search?q=%(query)s&first=%(start)d",
    'search_num'    : "http://www.bing.%(tld)s/search?q=%(query)s&first=%(start)d",
    'next_page_num' : "http://www.bing.%(tld)s/search?q=%(query)s&first=%(start)d",
}

_defailt_timeout = _section.getfloat('timeout')


class BingSearchEngine(BaseSearchEngine):

    def __init__(self, alias, urls, timeout, **kw):
        super(BingSearchEngine, self).__init__(alias, urls, timeout, **kw)


def search(query, logger, errorlog, **kw):
    silence = kw.get('silence') and True or False

    se = BingSearchEngine(_section.get('alias'), _urls, _defailt_timeout, 
        parser=_section.get('parser'),
        tags=_section.get('tags'),
        parent=_section.get('parent'),
        trace=not silence
    )
    se._init_state(logger)

    try:
        return [x for x in se.search(query, **kw)]
    except:
        info = sys.exc_info()
        s = '%s:%s' % (info[0], info[1])
        if not silence:
            print(s)
        print_exception()

    return []


# When run as a script...
if __name__ == "__main__":
    from optparse import OptionParser, IndentedHelpFormatter

    class BannerHelpFormatter(IndentedHelpFormatter):
        "Just a small tweak to optparse to be able to print a banner."
        def __init__(self, banner, *argv, **argd):
            self.banner = banner
            IndentedHelpFormatter.__init__(self, *argv, **argd)
        def format_usage(self, usage):
            msg = IndentedHelpFormatter.format_usage(self, usage)
            return '%s\n%s' % (self.banner, msg)

    errorlog = open(os.path.join(basedir, 'traceback.log'), 'a')

    # Parse the command line arguments.
    formatter = BannerHelpFormatter(
        "Python script to use the Bing search engine\n"
        "By Mario Vilas (mvilas at gmail dot com)\n"
    )
    parser = OptionParser(formatter=formatter)
    parser.set_usage("%prog [options] query")
    parser.add_option("--tld", metavar="TLD", type="string", default="com",
                      help="top level domain to use [default: com]")
    parser.add_option("--lang", metavar="LANGUAGE", type="string", default="en",
                      help="produce results in the given language [default: en]")
    parser.add_option("--num", metavar="NUMBER", type="int", default=10,
                      help="number of results per page [default: 10]")
    parser.add_option("--start", metavar="NUMBER", type="int", default=0,
                      help="first result to retrieve [default: 0]")
    parser.add_option("--stop", metavar="NUMBER", type="int", default=10,
                      help="last result to retrieve [default: 10]")
    parser.add_option("--pause", metavar="SECONDS", type="float", default=2.0,
                      help="pause between HTTP requests [default: 2.0]")
    parser.add_option("--trace", dest="trace",
                      action="store_true", default=False, help="trace parsing")
    parser.add_option("--all", dest="only_standard",
                      action="store_false", default=True,
                      help="grab all possible links from result pages")
    options, args = parser.parse_args()
    query = ' '.join(args)
    if not query:
        parser.print_help()
        sys.exit(2)
    
    params = [(k, v) for (k, v) in options.__dict__.items() if not k.startswith('_')]
    params = dict(params)

    print('options[{%s}]' % ', '.join(["'%s': %s" % (x, str(params.get(x))) for x in sorted(params)]))

    # Run the query.
    for url in search(query, None, errorlog, **params):
        print(url)

    print('--> End of script.')

    errorlog.close()