---
type: Capability
title: Search and read the library
description: Find pages by meaning or keywords, read a page, list pages by type or
  tag, follow links between concepts.
id: knowledge.search
module: knowledge
tools: [knowledge-base__kb_find, knowledge-base__kb_graph, knowledge-base__kb_list,
  knowledge-base__kb_read]
tool_patterns: [knowledge-base__kb_find, knowledge-base__kb_read, knowledge-base__kb_list,
  knowledge-base__kb_graph]
available: 4
confirm: false
always: false
examples: ['co wiem o PySpark?', znajdź notatki o SQL, show me the concept of delta
    lake]
used_by: ['skill:knowledge.study-session']
tags: [capability, knowledge]
timestamp: '2026-09-25T14:22:57+02:00'
---

# Search and read the library

Find pages by meaning or keywords, read a page, list pages by type or tag, follow links between concepts.

Module: [knowledge](../modules/knowledge.md)

## Tools
- [kb_find](../tools/knowledge-base/kb-find.md) - knowledge-base, read
- [kb_graph](../tools/knowledge-base/kb-graph.md) - knowledge-base, read
- [kb_list](../tools/knowledge-base/kb-list.md) - knowledge-base, read
- [kb_read](../tools/knowledge-base/kb-read.md) - knowledge-base, read

## Used by
- skill:knowledge.study-session

## Example requests
- co wiem o PySpark?
- znajdź notatki o SQL
- show me the concept of delta lake
