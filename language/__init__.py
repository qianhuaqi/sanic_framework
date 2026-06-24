#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

from app.errors.catalog import normalize_locale_name, parse_error_code_catalog


def lang(sec=None, opt=None, s="zh-CN"):
    if opt and not sec:
        return None

    locale_root = Path(__file__).resolve().parent
    locale_name = normalize_locale_name(s)
    catalog = parse_error_code_catalog(locale_root)

    if sec:
        section_items = {
            record.code: record.messages.get(locale_name)
            for record in catalog
            if record.section == sec
        }
        if opt:
            return section_items.get(opt)
        return section_items or None

    sections = {
        record.section: {
            record.code: record.messages.get(locale_name)
            for record in catalog
            if record.section == section
        }
        for section in sorted({record.section for record in catalog})
    }
    return sections or None
