# -*- coding: utf-8 -*-

import os
import configparser
import logging
import pytz

from app.commandline import get_command_line

basedir = '.' #os.path.abspath(os.path.dirname(__file__))

CONFIG_FILE = os.path.join(basedir, 'config.txt')
already_parsed = False
logger = logging.getLogger('SEScraper')

IsDebug = 1
IsDeepDebug = 1
IsTrace = 1
IsDBCheck = 0

Config = {
    'SCRAPING': {
        # Whether to scrape with own ip address or just with proxies
        'use_own_ip': True,
        # which scrape_method to use
        'scrape_method': 'http'
    },
    'RUNTIME': {
        # DB path & default engine
        'sqlalchemy_database_uri' : 'sqlite:///' + os.path.join(basedir, 'storage', 'app.db'),
        # Local timezone
        #'local_tz' : pytz.timezone('Europe/Moscow'),
        # Path to application errorlog
        'errorlog' : os.path.join(basedir, 'traceback.log')
    }
}

LOCAL_TZ = '' #pytz.timezone('Europe/Moscow')

USER_AGENTS = ( \
    'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0)',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/600.2.5 (KHTML, like Gecko) Version/8.0.2 Safari/600.2.5',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 8_1_2 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B440 Safari/600.1.4',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko',
    'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (iPad; CPU OS 8_1_2 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B440 Safari/600.1.4',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/600.2.5 (KHTML, like Gecko) Version/7.1.2 Safari/537.85.11',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Windows NT 6.1; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/600.1.25 (KHTML, like Gecko) QuickLook/5.0',
    'Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 7_1_2 like Mac OS X) AppleWebKit/537.51.2 (KHTML, like Gecko) Version/7.0 Mobile/11D257 Safari/9537.53',
    'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Windows NT 5.1; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/600.1.25 (KHTML, like Gecko) Version/8.0 Safari/600.1.25',
    'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0)',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/600.1.17 (KHTML, like Gecko) Version/7.1 Safari/537.85.10',
    'Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:35.0) Gecko/20100101 Firefox/35.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/534.59.10 (KHTML, like Gecko) Version/5.1.9 Safari/534.59.10',
    'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; WOW64; Trident/6.0)',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10) AppleWebKit/600.1.25 (KHTML, like Gecko) Version/8.0 Safari/600.1.25',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.99 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/39.0.2171.65 Chrome/39.0.2171.65 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_5) AppleWebKit/537.78.2 (KHTML, like Gecko) Version/6.1.6 Safari/537.78.2',
    'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/600.3.10 (KHTML, like Gecko) Version/8.0.3 Safari/600.3.10',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B411 Safari/600.1.4',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (iPad; CPU OS 7_1_2 like Mac OS X) AppleWebKit/537.51.2 (KHTML, like Gecko) Version/7.0 Mobile/11D257 Safari/9537.53',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.99 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 8_1_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B435 Safari/600.1.4',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/537.78.2 (KHTML, like Gecko) Version/7.0.6 Safari/537.78.2',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:33.0) Gecko/20100101 Firefox/33.0',
    'Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; Touch; rv:11.0) like Gecko',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:31.0) Gecko/20100101 Firefox/31.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 7_1_1 like Mac OS X) AppleWebKit/537.51.2 (KHTML, like Gecko) Version/7.0 Mobile/11D201 Safari/9537.53',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 8_0_2 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12A405 Safari/600.1.4',
    'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.45 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.0; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 8_1_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B436 Safari/600.1.4',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 8_1_2 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) GSA/5.1.42378 Mobile/12B440 Safari/600.1.4',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 8_1_2 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) CriOS/39.0.2171.50 Mobile/12B440 Safari/600.1.4',
    'Mozilla/5.0 (Windows NT 6.2; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)',
    'Mozilla/5.0 (iPad; CPU OS 8_1_2 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) CriOS/39.0.2171.50 Mobile/12B440 Safari/600.1.4',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.99 Safari/537.36',
    'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/600.2.5 (KHTML, like Gecko) Version/6.2.2 Safari/537.85.11',
    'Mozilla/5.0 (iPad; CPU OS 8_1_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B435 Safari/600.1.4',
    'Mozilla/5.0 (Linux; Android 5.0.1; Nexus 5 Build/LRX22C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.93 Mobile Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:35.0) Gecko/20100101 Firefox/35.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:31.0) Gecko/20100101 Firefox/31.0',
    'Mozilla/5.0 (Windows NT 6.1; rv:35.0) Gecko/20100101 Firefox/35.0',
)

ADDRESS_KEYS = ( \
    (2, 'россия'),
    (2, 'москва'),
    (3, 'московск'),
    (3, 'город'),
    (3, 'область'),
    (5, 'улица'),
    (4, 'проезд'),
    (4, 'шоссе'),
    (5, 'обл.'),
    (5, 'ул.'),
    (5, 'г.'),
    (5, 'стр.'),
    (5, 'ш.'),
    (5, 'д.'),
    (5, 'пер.'),
    (3, 'офис'),
    (10,'почтовый индекс'),
)

MANAGER_KEYS = ( \
    (10,'генеральный директор'),
    (10,'главный бухгалтер'),
    (10,'председатель'),
    (10,'гендиректор'),
    (8, 'руководитель'),
    (8, 'директор'),
    #(8, 'бухгалтер'),
    (8, 'учредители'),
    (8, 'учредитель'),
    #(6, 'собственник'),
    (6, 'владелец'),
    (6, 'владельцы'),
    #(5, 'менеджер'),
    (8, 'ФИО руководителя'),
    #(5, 'ФИО'),
)

FIO_KEYS = { \
    'F' : 'ов:ев:ский:ич:ко:ин:ян:дзе:янц:енц:унц:онц:уни:гу:ко:юк:ош:'
          'ова:ева:ская',
    'O' : 'ов:ев:ин:вич:'
          'ова:ева:ина:вна:ична',
}

BLOCK_TYPES = ( '.pdf', '.swg', '.gif', '.jpg', '.jpeg', '.png', '.xls', 'xlsx', '.doc', '.docx', '.rar', '.zip', )
BLOCK_URLS  = ( \
    '3goroda.ru/page/letter',
    'avia.tutu',
    'audito.xyz',
    'academ-clinic.ru',
    'gis-lab.info',
    'gruzoko.link',
    'b2b-project.ru/b2b/tenders',
    'b2b-project.ru/b2b/news',
    'b2b-project.ru/b2b/research',
    'b2bpoisk.ru/b2b/tenders/tenders',
    'b2bpoisk.ru/b2b/tenders/news',
    'b2bpoisk.ru/b2b/tenders/research',
    'partnerscheck.ru/ru/component/kadarbitr',
    'pfrf.ru',
    'russiatelefon.com/kod',
    'znaybiznes.ru/tenders',
)

BLOCK_DOMAINS  = ( \
    'beeline',
    'bing',
    'chrome',
    'facebook',
    'fitness96',
    'forum',
    'gis-lab',
    'google',
    'habrahabr',
    'indeed',
    'iskalko',
    'kinopoisk',
    'megafon',
    'microsoft',
    'mozilla',
    'mts.ru',
    'nedva.lol',
    'opera',
    'partnerscheck',
    'thesims3',
    'twitter',
    'voopiik-don',
    'vpnews',
    'wikipedia',
    'yandex',
    'youtube',
)

TAG_RATING = { \
    'url'         : 1000,
    'title'       : 200,
    'description' : 100,
    'keywords'    : 100,
    'property'    : 50,
    'default'     : 1,
}

UNUSED_TAGS   = ( 'script', 'noscript', 'style', 'svg', 'img', )
UNUSED_EMAILS = ( \
    'rating@mail.ru',
    'online@prima-inform.ru',
    'webmaster',
    'admin',
    'support',
    'robot',
)

SEARCH_ENGINES = ('ask', 'bing', 'google', 'mail', 'rambler', 'yahoo', 'yandex',)
SEARCH_MODES = ('email', 'phone', 'address', 'manager',)
SEARCH_OPTIONS = ('top', 'string', 'unique',)

PAGE_SIZE = ((50, '50'), (100, '100'), (250, '250'), (500, '500'), (1000, '1000'), (0, 'Все'),)

FILTER_COLUMNS = { \
    'NAME'    : (0, 'Ответчик'),
    'CLAIM'   : (1, 'Сумма иска'),
    'ADDRESS' : (2, 'Адрес'),
    'NUMBER'  : (3, 'Номер дела'),
}

STATUS = { \
    'LOAD'    : (0, 'Загрузка',),
    'CONTROL' : (1, 'Проверяйте!',),
    'READY'   : (2, 'Готово',),
    'OK'      : (3, 'Выполнено',),
    'FAILED'  : (4, 'Брак',),
}


class InvalidConfigurationException(Exception):
    pass


def parse_config(parse_command_line=True):
    """Parse and normalize the config file and return a dictionary with the arguments.

    There are several places where GoogleScraper can be configured. The configuration is
    determined (in this order, a key/value pair emerging further down the list overwrites earlier occurrences)
    from the following places:
      - Program internal configuration found in the global variable Config in this file
      - Configuration parameters given in the config file CONFIG_FILE
      - Params supplied by command line arguments

    So for example, program internal params are overwritten by the config file which in turn
    are shadowed by command line arguments.

    """
    global Config, CONFIG_FILE

    cargs = None
    cfg_parser = configparser.RawConfigParser()
    
    # Add internal configuration
    cfg_parser.read_dict(Config)

    if parse_command_line:
        cargs = get_command_line()

    if parse_command_line:
        cfg_file_cargs = cargs['GLOBAL'].get('config_file')
        if cfg_file_cargs and os.path.exists(cfg_file_cargs):
            CONFIG_FILE = cfg_file_cargs

    # Parse the config file
    try:
        with open(CONFIG_FILE, 'r', encoding='utf8') as cfg_file:
            cfg_parser.read_file(cfg_file)
    except Exception as e:
        logger.error('Exception trying to parse config file {}: {}'.format(CONFIG_FILE, e))

    logger.setLevel(cfg_parser['GLOBAL'].get('debug', 'INFO'))

    # add configuration parameters retrieved from command line
    if parse_command_line:
        cfg_parser = update_config(cargs, cfg_parser)

    # and replace the global Config variable with the real thing
    Config = cfg_parser

    # if we got extended config via command line, update the Config
    # object accordingly.
    if parse_command_line:
        if cargs['GLOBAL'].get('extended_config'):
            d = {}
            for option in cargs['GLOBAL'].get('extended_config').split('|'):
                assert ':' in option, '--extended_config "key:option, key2: option"'
                key, value = option.strip().split(':')
                d[key.strip()] = value.strip()

            for section, section_proxy in Config.items():
                for key, option in section_proxy.items():
                    if key in d and key != 'extended_config':
                        Config.set(section, key, str(d[key]))

def update_config_with_file(external_cfg_file):
    """Updates the global Config with the configuration of an
    external file.

    Args:
        external_cfg_file: The external configuration file to update from.
    """
    if external_cfg_file and os.path.exists(external_cfg_file):
        external = configparser.RawConfigParser()
        external.read_file(open(external_cfg_file, 'rt'))
        external.remove_section('DEFAULT')
        update_config(dict(external))

def parse_cmd_args():
    """Parse the command line"""
    global Config
    update_config(get_command_line(), Config)

def get_config(force_reload=False, parse_command_line=True):
    """Returns the Scraper configuration.

    Args:
        force_reload: If true, ignores the flag already_parsed
    
    Returns:
        The configuration after parsing it.
    """
    global already_parsed
    if not already_parsed or force_reload:
        parse_config(parse_command_line=parse_command_line)
        already_parsed = True
    return Config

def update_config(d, target=None):
    """Updates the config with a dictionary.

    In comparison to the native dictionary update() method,
    update_config() will only extend or overwrite options in sections. It won't forget
    options that are not explicitly specified in d.

    Will overwrite existing options.

    Args:
        d: The dictionary to update the configuration with.
        target: The configuration to be updated.

    Returns:
        The configuration after possibly updating it.
    """
    if not target:
        global Config
    else:
        Config = target

    for section, mapping in d.items():
        if not Config.has_section(section) and section != 'DEFAULT':
            Config.add_section(section)

        for option, value in mapping.items():
            Config.set(section, option, str(value))

    return Config

# @todo: Config is overwritten here. Check if this approach is wanted or a bug
Config = get_config(parse_command_line=False)


# Predefined settings
#SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'storage', 'app.db.4') #Config['RUNTIME'].get('sqlalchemy_database_uri')
#SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:admin@localhost/se0'
SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:admin@localhost/se0'
ERRORLOG = Config['RUNTIME'].get('errorlog')

KAD_SERVICES = { \
    'getJudgeSuggest':"Suggest/Judges",
    'getCourtSuggest':"Suggest/Courts",
    'getCasesSuggest':"Suggest/CaseNum",
    'getInstances':"Kad/SearchInstances",
    'getSuggest':"Suggest/Common",
    'getInstanceDocuments':"Kad/InstanceDocuments",
    'getInstanceDocumentsPage':"Kad/InstanceDocumentsPage",
    'getEProductionCourts':"Kad/GetEProductionCourts",
    'getEProductionDocumentTypes':"Kad/GetEProductionDocumentTypes",
    'getCard':"Kad/Card",
    'getCalendar':"Kad/FullCard",
    'getCalendarYearEvents':"Calendar/Calendar",
    'getCalendarEvents':"Calendar/GetEvents",
    'getCalendarDocuments':"Calendar/GetDocuments",
    'getCaseDocuments':"Kad/CaseDocuments",
    'getCaseDocumentsPage':"Kad/CaseDocumentsPage",
    'getSidesByName':"Suggest/GetSidesByName",
    'missingCase':"Kad/MissingCase",
    'sideDocuments':"Kad/SideDocuments",
    'documentChain':"Kad/DocumentChain",
    'checkCode':"SimpleJustice/CheckCode",
    'createNewDocument':"SimpleJustice/Create",
    'editDocument':"SimpleJustice/Update",
    'deleteDocument':"SimpleJustice/Delete",
    'deleteAct':"Kad/MarkDocDeleted",
    'recourseAttachments':"SimpleJustice/RecourseAttachments",
    'sessionProtocols':"Kad/SessionProtocols",
    'saveDocumentFile':"IntermediateStorage/Save",
    'saveDocumentImage':"IntermediateStorage/SaveImage",
    'saveDocumentPdfBase64':"IntermediateStorage/SaveBase64Pdf",
    'uploadStatus':"SimpleJustice/UploadStatus",
    'suggestSystemSpecific':"Suggest/SystemSpecific",
    'saveAppealDocument':"SimpleJustice/CreateThanProceduralAppeal",
    'GetAppealReceivedFromTypes':"Kad/GetAppealReceivedFromTypes",
    'GetAppealReceivedToTypes':"Kad/GetAppealReceivedToTypes",
    'getRosRegistryDicts':"Smev/RosRegistryDicts",
    'getDecisions':"Ras/Search",
    'getTimetableMonth':"Rad/TimetableMonth",
    'getTimetableDay':"Rad/TimetableDay",
    'getSessionPauses':"Recess/GetSessionPauses",
    'getSubscriptions':"Guard/Subscriptions",
    'setSubscription':"Guard/Subscribe",
    'setSubscriptionFromCard':"Guard/Subscribe2",
    'removeSubscription':"Guard/Unsubscribe",
    'logOn':"Account/LogOn",
    'logOff':"Account/LogOff",
    'registerUser':"Account/Register",
    'activateEmail':"Account/SendValidationEmail",
    'remindPassword':"Account/SendRestorePasswordMail",
    'changePassword':"Account/ChangePassword",
    'changeVpLogin':"Account/UpdateVpProfile",
    'restorePassword':"Account/RestorePassword",
    'getCabinets':"Schedule/GetCabinets",
    'getCabinetsList':"Schedule/GetCabinetsList",
    'getCourtGroups':"Schedule/GetCourtGroups",
    'getCourtSessions':"Schedule/CourtSessions",
    'getCabinetSessions':"Schedule/GetCabinetSessions",
    'getSessionDetails':"Schedule/GetSessionDetails",
    'getCaseSessions':"Schedule/CaseSessions",
    'updateSession':"Schedule/UpdateSession",
    'uniteSessions':"Schedule/UniteSessions",
    'getResolutionTypes':"Schedule/ResolutionTypes",
    'markSides':"Schedule/MarkSidePresent",
    'setSessionsOrder':"Schedule/SetSessionsOrder",
    'moveSession':"Schedule/MoveSession",
    'cancelSession':"Schedule/CancelSession",
    'saveGroup':"Schedule/SaveGroup",
    'setCabinetArchiveState':"Schedule/SetCabinetArchiveState",
    'setCabinetDisplayName':"Schedule/SetCabinetDisplayName",
    'clearCache':"Schedule/ClearCache",
    'setPhoneSubscription':"Schedule/RequestSubscriptionCode",
    'confirmPhoneSubscription':"Schedule/ConfirmSubscription",
    'path':"",
    'host':"",
    'img_host':"Content/Static/img/Presidium/",
    'video_host':"Content/Static/video/Presidium/",
    'css_host':"Content/Static/css/Presidium/",
    'js_host':"Content/Static/js/Presidium/",
    'getPresidiumMonths':"Presidium/PresidiumMonths",
    'getPresidiumSessions':"Presidium/Sessions",
    'sendSubscriptionPhoneNumber':"Presidium/RequestCode",
    'sendConfirmationCode':"Presidium/ConfirmPhone",
    'setPresidiumSubscription':"Presidium/Subscribe",
    'startPresidiumPause':"Presidium/StartPause",
    'stopPresidiumPause':"Presidium/FinishPause",
    'setPresidiumVideoLink':"Schedule/VideoLink"
}

KAD_CASE_KEYS = ('Judge', 'CaseId', 'CaseType', 'CaseNumber', 'CourtName', 'Date', 'IsSimpleJustice',) # 'Plaintiffs', 'Respondents', 
KAD_PARTICIPANT_KEYS = ('Name', 'Inn', 'Address', 'OrganizationForm',) # 'SubjectCategories'
KAD_PLAINTIFF_KEYS = ('Participants', 'Count',)
KAD_RESPONDENT_KEYS = ('Participants', 'Count',)

KAD_DOCUMENT_KEYS = ( \
    'ActualDate', 'AdditionalInfo', 'Addressee', 'AppealDate', 'AppealDescription', 'AppealState', 'AppealedDocuments', 
    'CanBeDeleted', 'CaseId', 'ClaimSum', 'Comment', 'Content', 'ContentTypes', 'ContentTypesIds', 'CourtName', 'CourtTag', 
    'Date', 'DecisionType', 'DecisionTypeName', 'Declarers', 'DelDate', 'DelReason', 'DisplayDate', 'DocSession', 'DocStage', 
    'DocumentTypeId', 'DocumentTypeName', 'FileName', 'FinishInstance', 'GeneralDecisionType', 'HasSignature', 'HearingDate', 
    'HearingPlace', 'Id', 'InstStage', 'InstanceId', 'InstanceLevel', 'IsAct', 'IsDeleted', 'IsExceptionRulesDocumentType', 
    'IsPresidiumSessionEvent', 'IsSimpleJustice', 'IsStart', 'Judges', 'LinkedSideIds', 'PublishDate', 'PublishDisplayDate', 
    'ReasonDocumentId', 'RosRegNum', 'SignatureInfo', 'Signer', 'SimpleJusticeFileState', 'SourceSystem', 'SystemDocumentType', 
    'Type', 'UseShortCourtName', 'ViewsCount', 'WithAttachment',
)

KAD_DECLARERS_KEYS = ('OrganizationId', 'Type', 'Inn', 'Address', 'Id', 'Ogrn', 'Organization',)
