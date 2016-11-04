# -*- coding: utf-8 -*-

from __future__ import print_function

import sys
import codecs
import datetime
import traceback

try:
    from types import UnicodeType, StringType
    StringTypes = (UnicodeType, StringType,)
except:
    StringTypes = (str,)

from config import Config, ERRORLOG as errorlog, IsDebug, IsDeepDebug

default_encoding = 'cp1251'
default_unicode = 'utf8'
default_print_encoding = 'cp866' # 'UTF-8' sys.stdout.encoding

IsDisableOutput = 0

ansi = not sys.platform.startswith("win")
is_v3 = sys.version_info[0] > 2 and True or False

if is_v3:
    from imp import reload

EOR = '\r\n'
EOL = '\n'

rus_eng = ( \
    'А:A',
    'Б:B',
    'В:V',
    'Г:G',
    'Д:D',
    'Е:E',
    'Ё:YO',
    'Ж:ZH',
    'З:Z',
    'И:I',
    'Й:Y',
    'К:K',
    'Л:L',
    'М:M',
    'Н:N',
    'О:O',
    'П:P',
    'Р:R',
    'С:S',
    'Т:T',
    'У:U',
    'Ф:F',
    'Х:H',
    'Ц:C',
    'Ч:CH',
    'Ш:SH',
    'Щ:SCH',
    'Ъ:',
    'Ы:I',
    'Ь:',
    'Э:E',
    'Ю:YU',
    'Я:YA',
)

def _pout(s, **kw):
    if not is_v3:
        print(s, end='end' in kw and kw.get('end') or None)
        if 'flush' in kw and kw['flush'] == True:
            sys.stdout.flush()
    else:
        print(s, **kw)


##
## Класс для вывода данных в файл или на консоль
##

class Logger():
    
    def __init__(self, to_file=None, encoding=default_unicode, mode='w+', bom=True, end_of_line=EOL):
        self.is_to_file = to_file and 1 or 0
        self.encoding = encoding
        self.fo = None
        self.end_of_line = end_of_line

        if IsDisableOutput and to_file:
            pass
        elif to_file:
            self.fo = codecs.open(to_file, encoding=self.encoding, mode=mode)
            if bom:
                self.fo.write(codecs.BOM_UTF8.decode(self.encoding))
            self.out(to_file, console_forced=True) #_pout('--> %s' % to_file)
        else:
            pass

    def get_to_file(self):
        return self.fo

    def set_default_encoding(self, encoding=default_unicode):
        if sys.getdefaultencoding() == 'ascii':
            reload(sys)
            sys.setdefaultencoding(encoding)
        _pout('--> %s' % sys.getdefaultencoding())

    def out(self, line, console_forced=False, without_decoration=False):
        if not line:
            return
        elif console_forced or not (self.fo or self.is_to_file):
            mask = '%s' % (not without_decoration and '--> ' or '')
            try:
                _pout('%s%s' % (mask, line))
            except:
                if is_v3:
                    pass
                elif type(line) is UnicodeType:
                    v = ''
                    for x in line:
                        try:
                            _pout(x, end='')
                            v += x.encode(default_encoding, 'ignore')
                        except:
                            v += '?'
                    _pout('')
                else:
                    _pout('%s%s' % (mask, line.decode(default_encoding, 'ignore')))
        elif IsDisableOutput:
            return
        else:
            if type(line) in StringTypes:
                try:
                    self.fo.write(line)
                except:
                    if is_v3:
                        return
                    try:
                        self.fo.write(unicode(line, self.encoding))
                    except:
                        try:
                            self.fo.write(line.decode(default_encoding)) #, 'replace'
                        except:
                            raise
                if not line == self.end_of_line:
                    self.fo.write(self.end_of_line)

    def progress(self, line=None, mode='continue'):
        if mode == 'start':
            _pout('--> %s:' % (line or ''), end=' ')
        elif mode == 'end':
            _pout('', end='\n')
        else:
            _pout('#', end='', flush=True)

    def close(self):
        if IsDisableOutput:
            return
        if not self.fo:
            return
        self.fo.close()

##
## Утилита для вывода в читабельный вид на консоль
##

def setup_console(sys_enc=default_unicode):
    """
    Set sys.defaultencoding to `sys_enc` and update stdout/stderr writers to corresponding encoding
    .. note:: For Win32 the OEM console encoding will be used istead of `sys_enc`
    http://habrahabr.ru/post/117236/
    http://www.py-my.ru/post/4bfb3c6a1d41c846bc00009b
    """
    global ansi
    reload(sys)
    
    try:
        if sys.platform.startswith("win"):
            import ctypes
            enc = "cp%d" % ctypes.windll.kernel32.GetOEMCP()
        else:
            enc = (sys.stdout.encoding if sys.stdout.isatty() else
                        sys.stderr.encoding if sys.stderr.isatty() else
                            sys.getfilesystemencoding() or sys_enc)

        sys.setdefaultencoding(sys_enc)

        if sys.stdout.isatty() and sys.stdout.encoding != enc:
            sys.stdout = codecs.getwriter(enc)(sys.stdout, 'replace')

        if sys.stderr.isatty() and sys.stderr.encoding != enc:
            sys.stderr = codecs.getwriter(enc)(sys.stderr, 'replace')
    except:
        pass

def log(file_name, items, mode='a+', bom=False, end_of_line=EOL):
    so = Logger(file_name, mode=mode, bom=bom, end_of_line=end_of_line)
    for x in items:
        so.out(str(x))
    so.out(EOL)
    so.close()

def dump(file_name, content, mode='w+'):
    fo = codecs.open(file_name, encoding=default_unicode, mode=mode)
    fo.write(content)
    fo.close()

def print_to(f, v, mode='a', request=None):
    items = not isinstance(v, (list, tuple)) and [v] or v
    fo = open(f, mode=mode)
    for text in items:
        if IsDeepDebug:
            print(text)
        try:
            if request:
                fo.write('%s--> %s%s' % (EOL, request.url, EOL))
            fo.write(text)
            fo.write(EOL)
        except Exception as err:
            pass
    fo.close()

def print_exception():
    try:
        print_to(errorlog, '>>> %s: Exception%s' % (datetime.datetime.now().strftime(Config['DEFAULT'].get('FULL_TIMESTAMP')), EOL))
        traceback.print_exc(file=open(errorlog, 'a'))
    except:
        pass

def conv_rus_eng(s):
    out = ''
    abc = dict(map(lambda x: x.split(':'), rus_eng))
    for x in s:
        out += abc.get(x.upper()) or x
    return out.lower()
