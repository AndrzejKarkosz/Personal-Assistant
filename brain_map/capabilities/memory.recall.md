---
type: Capability
title: Recall past sessions and facts
description: Search and read Alfred's own memory - session summaries, the change log,
  facts about the user.
id: memory.recall
module: memory
tools: [memory_read, memory_search]
tool_patterns: [memory_search, memory_read]
confirm: false
always: false
available: 2
examples: ['o czym rozmawialiśmy wczoraj?', 'co zrobiłeś pod moją nieobecność?']
used_by: ['module:bookings', 'skill:bookings.restaurant-table', 'module:calendar',
  'skill:calendar.daily-brief', 'module:tasks', 'module:training', 'skill:training.training-week',
  'module:weight', 'skill:weight.weight-goal']
tags: [capability, memory]
timestamp: '2026-10-04T19:05:26+02:00'
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
- module:training
- skill:training.training-week
- module:weight
- skill:weight.weight-goal

## Example requests
- o czym rozmawialiśmy wczoraj?
- co zrobiłeś pod moją nieobecność?
