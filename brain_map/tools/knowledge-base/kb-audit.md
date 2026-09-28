---
type: Tool
title: kb_audit
description: 'OKF conformance and index integrity -- the checks kb_health does not
  do: unparseable frontmatter, missing or out-of-vocabulary `type`, missing required
  fields, pages absent from their directory index, drift between a page''s index descriptio'
id: knowledge-base__kb_audit
server: knowledge-base
kind: mcp
short: kb_audit
capabilities: [knowledge.learning]
modules: [knowledge]
side_effect: read
requires_confirmation: false
status: online
params: []
tags: [tool, knowledge-base]
timestamp: '2026-09-28T18:45:56+02:00'
---

# kb_audit

OKF conformance and index integrity -- the checks kb_health does not do: unparseable frontmatter, missing or out-of-vocabulary `type`, missing required fields, pages absent from their directory index, drift between a page's index description and its frontmatter description, `verified` not attributable to a human, and invalid `mastery` values.

Server: [knowledge-base](../../servers/knowledge-base.md)

## Capabilities
- [Learning progress](../../capabilities/knowledge.learning.md) (`knowledge.learning`)
