---
type: Module
title: Our past conversations
description: What we talked about before, what Alfred did in earlier sessions, what
  was decided, remember a fact about me, forget or correct something.
id: memory
capabilities: [memory.recall, memory.remember]
uses: [tasks.manage]
skills: []
servers: [alfred]
examples: ['o czym rozmawialiśmy wczoraj?', 'co ustaliliśmy w sprawie wyjazdu?', 'zapamiętaj,
    że nie jem mięsa', what did you do while I was away]
enabled: true
model: null
effort: null
tags: [module]
timestamp: '2026-09-30T17:50:37+02:00'
---

# Our past conversations

What we talked about before, what Alfred did in earlier sessions, what was decided, remember a fact about me, forget or correct something.

## Capabilities
- [Recall past sessions and facts](../capabilities/memory.recall.md) (`memory.recall`)
- [Remember a fact about the user](../capabilities/memory.remember.md) (`memory.remember`)

## Borrowed capabilities
- [Manage tasks and reminders](../capabilities/tasks.manage.md) (`tasks.manage`)

## Connected servers
- [alfred](../servers/alfred.md)

## Example requests
- o czym rozmawialiśmy wczoraj?
- co ustaliliśmy w sprawie wyjazdu?
- zapamiętaj, że nie jem mięsa
- what did you do while I was away
