---
type: Tool
title: get_profile
description: 'Get the user''s current settings in one call: timezone (plus local date
  and time), widget language, preferred weight unit, preferred length unit, whether
  in-chat widgets are shown, and whether alcohol tracking is on — everything set_timezone'
id: nutrition__get_profile
server: nutrition
kind: mcp
short: get_profile
capabilities: [weight.goals]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: []
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# get_profile

Get the user's current settings in one call: timezone (plus local date and time), widget language, preferred weight unit, preferred length unit, whether in-chat widgets are shown, and whether alcohol tracking is on — everything set_timezone, set_language, set_weight_unit, set_length_unit, set_widget_display and set_alcohol_tracking each control. Prefer this over guessing a setting from context, and use it once instead of calling several separate settings tools when you need more than one.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Weight and nutrition goals](../../capabilities/weight.goals.md) (`weight.goals`)
