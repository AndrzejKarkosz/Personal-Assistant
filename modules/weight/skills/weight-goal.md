---
name: Set the weight goal
description: Interview about the weight goal (one question at a time) and set target weight, calories and macros
uses: [weight.goals, weight.read, training.status, memory.recall, memory.remember]
---
1. Read get_nutrition_goals, get_goal_progress and memory_search "waga cel" - note what is already known.
2. Ask ONE question per turn for what is missing: current weight, height, age, target weight, by when, training
   hours a week (training_status has the plan), a normal day of eating, foods he will not give up.
3. When everything is known, propose in at most four sentences: target weight and pace (~0.5% body weight a week),
   daily kcal (deficit 300-500 kcal, more food on long training days), protein 1.8-2.0 g/kg, carbs and fat.
4. After his yes: set_nutrition_goals (calories, macros, target weight) and memory_remember why (category preference).
