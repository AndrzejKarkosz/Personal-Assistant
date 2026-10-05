---
type: Skill
title: Set the weight goal
description: Interview about the weight goal (one question at a time) and set target
  weight, calories and macros
id: weight.weight-goal
module: weight
uses: [weight.goals, weight.read, training.status, memory.recall, memory.remember]
tags: [skill, weight]
timestamp: '2026-10-04T19:05:26+02:00'
---

# Set the weight goal

Interview about the weight goal (one question at a time) and set target weight, calories and macros

Module: [weight](../modules/weight.md)

## Uses
- [Weight and nutrition goals](../capabilities/weight.goals.md) (`weight.goals`)
- [Diet and weight progress](../capabilities/weight.read.md) (`weight.read`)
- [Training plan and Strava](../capabilities/training.status.md) (`training.status`)
- [Recall past sessions and facts](../capabilities/memory.recall.md) (`memory.recall`)
- [Remember a fact about the user](../capabilities/memory.remember.md) (`memory.remember`)

## Procedure

1. Read get_nutrition_goals, get_goal_progress and memory_search "waga cel" - note what is already known.
2. Ask ONE question per turn for what is missing: current weight, height, age, target weight, by when, training
   hours a week (training_status has the plan), a normal day of eating, foods he will not give up.
3. When everything is known, propose in at most four sentences: target weight and pace (~0.5% body weight a week),
   daily kcal (deficit 300-500 kcal, more food on long training days), protein 1.8-2.0 g/kg, carbs and fat.
4. After his yes: set_nutrition_goals (calories, macros, target weight) and memory_remember why (category preference).
