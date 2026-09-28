---
type: Tool
title: kb_health
description: 'Graph-level state: the frontier (wanted but unwritten pages, ranked
  by how many pages want each -- a work queue, never an error list), orphans, `# Requires`
  cycles, draft and unverified counts, and pages per type.'
id: knowledge-base__kb_health
server: knowledge-base
kind: mcp
short: kb_health
capabilities: [knowledge.learning]
modules: [knowledge]
side_effect: read
requires_confirmation: false
status: online
params: []
tags: [tool, knowledge-base]
timestamp: '2026-09-25T14:22:57+02:00'
---

# kb_health

Graph-level state: the frontier (wanted but unwritten pages, ranked by how many pages want each -- a work queue, never an error list), orphans, `# Requires` cycles, draft and unverified counts, and pages per type.

Server: [knowledge-base](../../servers/knowledge-base.md)

## Capabilities
- [Learning progress](../../capabilities/knowledge.learning.md) (`knowledge.learning`)
