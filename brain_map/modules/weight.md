---
type: Module
title: Waga i dieta
description: Body weight, diet and food - logging meals, calories and macros, weigh-ins
  and body measurements, the weight goal and the nutrition goals, how eating supports
  training.
id: weight
capabilities: [weight.log, weight.read, weight.goals, weight.fix]
uses: [training.status, memory.recall, memory.remember]
skills: [weight.weight-goal]
servers: [alfred, nutrition, strava]
examples: [zjadłem owsiankę z bananem i dwa jajka, 'ważę dziś 82,4 kg', 'ile białka
    dziś zjadłem?', 'jak idzie mi redukcja?', obwód w pasie 88 cm, ustaw mi cel wagowy,
  what did I eat yesterday]
enabled: true
model: null
effort: null
tags: [module]
timestamp: '2026-10-04T21:08:27+02:00'
---

# Waga i dieta

Body weight, diet and food - logging meals, calories and macros, weigh-ins and body measurements, the weight goal and the nutrition goals, how eating supports training.

## Capabilities
- [Log meals, weight and measurements](../capabilities/weight.log.md) (`weight.log`)
- [Diet and weight progress](../capabilities/weight.read.md) (`weight.read`)
- [Weight and nutrition goals](../capabilities/weight.goals.md) (`weight.goals`)
- [Correct or delete entries](../capabilities/weight.fix.md) (`weight.fix`)

## Borrowed capabilities
- [Training plan and Strava](../capabilities/training.status.md) (`training.status`)
- [Recall past sessions and facts](../capabilities/memory.recall.md) (`memory.recall`)
- [Remember a fact about the user](../capabilities/memory.remember.md) (`memory.remember`)

## Skills
- [Set the weight goal](../skills/weight.weight-goal.md)

## Connected servers
- [alfred](../servers/alfred.md)
- [nutrition](../servers/nutrition.md)
- [strava](../servers/strava.md)

## Example requests
- zjadłem owsiankę z bananem i dwa jajka
- ważę dziś 82,4 kg
- ile białka dziś zjadłem?
- jak idzie mi redukcja?
- obwód w pasie 88 cm
- ustaw mi cel wagowy
- what did I eat yesterday
