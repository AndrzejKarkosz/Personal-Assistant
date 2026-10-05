---
type: Capability
title: Remember a fact about the user
description: Store a durable fact - a person, place, preference or project.
id: memory.remember
module: memory
tools: [memory_remember]
tool_patterns: [memory_remember]
confirm: false
always: false
available: 1
examples: ['zapamiętaj, że nie jem mięsa', my sister's name is Ola]
used_by: ['module:bookings', 'skill:bookings.restaurant-table', 'module:research',
  'module:training', 'module:weight', 'skill:weight.weight-goal']
tags: [capability, memory]
timestamp: '2026-10-04T19:05:26+02:00'
---

# Remember a fact about the user

Store a durable fact - a person, place, preference or project.

Module: [memory](../modules/memory.md)

## Tools
- [memory_remember](../tools/alfred/memory-remember.md) - alfred, write

## Used by
- module:bookings
- skill:bookings.restaurant-table
- module:research
- module:training
- module:weight
- skill:weight.weight-goal

## Example requests
- zapamiętaj, że nie jem mięsa
- my sister's name is Ola
