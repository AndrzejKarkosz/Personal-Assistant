---
type: Capability
title: Recall past sessions and facts
description: Search and read Alfred's own memory - session summaries, the change log,
  facts about the user.
id: memory.recall
module: memory
tools: [memory_read, memory_search]
tool_patterns: [memory_search, memory_read]
available: 2
confirm: false
always: false
examples: ['o czym rozmawialiśmy wczoraj?', 'co zrobiłeś pod moją nieobecność?']
used_by: ['module:bookings', 'skill:bookings.restaurant-table', 'module:calendar',
  'skill:calendar.daily-brief', 'module:tasks']
tags: [capability, memory]
timestamp: '2026-09-25T14:22:57+02:00'
---

# Recall past sessions and facts

Search and read Alfred's own memory - session summaries, the change log, facts about the user.

Module: [memory](../modules/memory.md)

## Tools
- [memory_read](../tools/alfred/memory-read.md) - alfred, read
- [memory_search](../tools/alfred/memory-search.md) - alfred, read

## Used by
- module:bookings
- skill:bookings.restaurant-table
- module:calendar
- skill:calendar.daily-brief
- module:tasks

## Example requests
- o czym rozmawialiśmy wczoraj?
- co zrobiłeś pod moją nieobecność?
