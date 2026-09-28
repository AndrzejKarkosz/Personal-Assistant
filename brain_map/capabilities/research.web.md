---
type: Capability
title: Search and read the web
description: Web search and reading pages for current information.
id: research.web
module: research
tools: [web_fetch, web_search]
tool_patterns: [web_search, web_fetch]
available: 2
confirm: false
always: false
examples: ['jaka jutro pogoda?', godziny otwarcia apteki, latest news about X]
used_by: ['module:bookings', 'skill:bookings.restaurant-table']
tags: [capability, research]
timestamp: '2026-09-25T14:22:57+02:00'
---

# Search and read the web

Web search and reading pages for current information.

Module: [research](../modules/research.md)

## Tools
- [web_fetch](../tools/anthropic/web-fetch.md) - anthropic, read
- [web_search](../tools/anthropic/web-search.md) - anthropic, read

## Used by
- module:bookings
- skill:bookings.restaurant-table

## Example requests
- jaka jutro pogoda?
- godziny otwarcia apteki
- latest news about X
