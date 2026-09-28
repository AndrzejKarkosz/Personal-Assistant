---
type: Tool
title: kb_find
description: Start here for any question about the bundle's subject matter. Returns
  ranked candidate pages with trust fields, matched against each page's retrieval
  key (title + description + section headings). Does NOT return page bodies -- follow
  up wi
id: knowledge-base__kb_find
server: knowledge-base
kind: mcp
short: kb_find
capabilities: [knowledge.search]
modules: [knowledge]
side_effect: read
requires_confirmation: false
status: online
params: [query, type, tag, status, limit]
tags: [tool, knowledge-base]
timestamp: '2026-09-28T18:45:56+02:00'
---

# kb_find

Start here for any question about the bundle's subject matter. Returns ranked candidate pages with trust fields, matched against each page's retrieval key (title + description + section headings). Does NOT return page bodies -- follow up with kb_read on the one or two that look right. `lexical_score` is IDF-weighted word overlap, not a probability: it cannot bridge languages and it misses paraphrase, so a low score is weak evidence of irrelevance.

Server: [knowledge-base](../../servers/knowledge-base.md)

## Capabilities
- [Search and read the library](../../capabilities/knowledge.search.md) (`knowledge.search`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `query` | string | yes | Natural-language question or keywords. |
| `type` | string |  | Restrict to one OKF type, e.g. Concept. |
| `tag` | string |  | Restrict to pages carrying this tag. |
| `status` | string |  |  |
| `limit` | integer |  |  |
