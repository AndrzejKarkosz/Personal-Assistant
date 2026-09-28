---
type: Capability
title: Remember a fact about the user
description: Store a durable fact - a person, place, preference or project.
id: memory.remember
module: memory
tools: [memory_remember]
tool_patterns: [memory_remember]
available: 1
confirm: false
always: false
examples: ['zapamiętaj, że nie jem mięsa', my sister's name is Ola]
used_by: ['module:bookings', 'skill:bookings.restaurant-table', 'module:research']
tags: [capability, memory]
timestamp: '2026-09-25T14:22:57+02:00'
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

## Example requests
- zapamiętaj, że nie jem mięsa
- my sister's name is Ola
