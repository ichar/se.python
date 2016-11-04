# -*- coding: utf-8 -*-

import argparse


def get_command_line(print_help=False):
    """Parse command line arguments when GoogleScraper is used as a CLI application.

    Args:
        print_help: If set to True, only prints the usage and immediately returns.

    Returns:
        The configuration as a dictionary that determines the behaviour of the app.
    """

    parser = None

    if parser and print_help:
        print(parser.format_help())
        return

    args = parser.parse_args()

    make_dict = lambda L: dict([(key, value) for key, value
                                in args.__dict__.items() if (key in L and value is not None)])

    return {
        'SCRAPING': make_dict(
            ['search_engines', 'scrape_method', 'num_pages_for_keyword', 'num_results_per_page', 'search_type',
             'keyword', 'keyword_file', 'num_workers']),
        'GLOBAL': make_dict(
            ['clean', 'debug', 'simulate', 'proxy_file', 'view_config', 'config_file', 'mysql_proxy_db', 'verbosity',
             'output_format', 'shell', 'output_filename', 'output_format', 'version', 'extended_config']),
        'OUTPUT': make_dict(['output_filename']),
    }
