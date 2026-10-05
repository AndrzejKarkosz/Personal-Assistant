---
type: Tool
title: lookup_barcode
description: Look up a packaged product's label nutrition by barcode via Open Food
  Facts. The figures come from the product's own label as transcribed by the Open
  Food Facts community, so they beat estimating — but they are not verified by this
  server a
id: nutrition__lookup_barcode
server: nutrition
kind: mcp
short: lookup_barcode
capabilities: [weight.log]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [barcode]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# lookup_barcode

Look up a packaged product's label nutrition by barcode via Open Food Facts. The figures come from the product's own label as transcribed by the Open Food Facts community, so they beat estimating — but they are not verified by this server and can be wrong, stale, or missing entirely. Pass the barcode digits (EAN/UPC, 8–14 digits). The user can type them, or you can read them from a photo of the package — transcribe the human-readable digits printed beneath the barcode. Returns the product name, serving, and macros, which you can then pass to log_meal scaled to the amount eaten. When Open Food Facts has computed them, it also returns the Nutri-Score (A–E, a nutritional-quality grade) and NOVA group (1–4, how processed the product is) — pass these along if the user is asking about the product's quality, not just its macros; they're omitted, not "n/a", when OFF hasn't computed one for that product. If no product is found, estimate from the product description, or from the label if the user can share it. Two gaps

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Log meals, weight and measurements](../../capabilities/weight.log.md) (`weight.log`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `barcode` | string | yes | Product barcode digits (EAN-8/13, UPC-A/E, or GTIN-14). Spaces and separators are ignored. |
