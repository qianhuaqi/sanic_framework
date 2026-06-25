#!/usr/bin/env python
# -*- coding: utf-8 -*-

import configparser
import os

from sanic_babel import Babel

from lingshu.error_codes import normalize_locale_name


def setup_i18n(app):
    locale_dir = app.config.get("LOCALE_DIR")
    if not locale_dir:
        raise ValueError("LOCALE_DIR is not configured in app.config")

    if not os.path.isabs(locale_dir):
        locale_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), locale_dir)

    babel = Babel(app)
    babel.localeselector(lambda: normalize_locale_name(app.config.get("LANGUAGE", "en-US")))

    app.config.update(
        {
            "BABEL_TRANSLATION_DIRECTORIES": locale_dir,
        }
    )


def get_i18n(path):
    result = {}
    for maindir, _subdir, file_name_list in os.walk(path):
        for filename in file_name_list:
            if os.path.splitext(filename)[1].lower() == ".ini":
                conf = configparser.ConfigParser()
                conf.read(os.path.join(maindir, filename), encoding="utf-8")
                for section in conf.sections():
                    items = {}
                    for option in conf.options(section):
                        items[option] = conf.get(section, option)
                    result[section] = items
    return result
