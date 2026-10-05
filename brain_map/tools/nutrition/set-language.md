---
type: Tool
title: set_language
description: 'Set the user''s UI language for in-chat widgets (dashboards, charts).
  Supported: ''en'' (English), ''de'' (Deutsch), ''es'' (Español), ''fr'' (Français),
  ''nl'' (Nederlands), ''pl'' (Polski), ''it'' (Italiano), ''uk'' (Українська), ''ja''
  (日本語). This does not'
id: nutrition__set_language
server: nutrition
kind: mcp
short: set_language
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: [locale]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# set_language

Set the user's UI language for in-chat widgets (dashboards, charts). Supported: 'en' (English), 'de' (Deutsch), 'es' (Español), 'fr' (Français), 'nl' (Nederlands), 'pl' (Polski), 'it' (Italiano), 'uk' (Українська), 'ja' (日本語). This does not change what language the model replies in — only the text rendered inside widget cards. Until one is set, widgets follow the host's language where it reports one, otherwise English.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `locale` | string | yes | One of: en, de, es, fr, nl, pl, it, uk, ja (ISO 639-1 code). |
