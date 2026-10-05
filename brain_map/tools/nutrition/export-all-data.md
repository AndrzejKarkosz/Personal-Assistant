---
type: Tool
title: export_all_data
description: Export EVERYTHING this server stores about the user — meals, water, weight,
  body measurements, nutrition goals and every dated change to them, profile settings,
  the sign-in account (email, sign-in methods and dates), tool-usage telemetry, t
id: nutrition__export_all_data
server: nutrition
kind: mcp
short: export_all_data
capabilities: []
modules: []
side_effect: read
requires_confirmation: false
status: online
params: []
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# export_all_data

Export EVERYTHING this server stores about the user — meals, water, weight, body measurements, nutrition goals and every dated change to them, profile settings, the sign-in account (email, sign-in methods and dates), tool-usage telemetry, the AI-app connections (OAuth grants, without the tokens) and the Apple Health sync connection with its 8-day record of what was sent — as a single ZIP archive (meals.csv, water.csv, weight.csv, body_measurements.csv, goals.csv, goals_history.csv, profile.csv, account.csv, telemetry.csv, connections.csv, health_sync.csv, plus a README.txt describing the columns, the units they are in, and what is not included) and return a private, time-limited download link (valid 60 minutes). Timestamps use the user's timezone if set, otherwise UTC; health_sync.csv rows use the timezone each day was counted in. Only meals.csv can be read back in; every other file is export-only. This is the server's only export path: it covers a full backup, an account takeout, and a request for the meal h

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities
