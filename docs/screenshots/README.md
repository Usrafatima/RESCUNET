# RescueNest Product Screenshots Guide

This directory is designated for capturing and storing high-resolution interface screenshots of the RescueNest platform for demonstrations and hackathon evaluations.

## Recommended Screenshots to Capture

| File Name | Screen / View | Route | Description & Caption |
| :--- | :--- | :--- | :--- |
| `01-citizen-sos-intake.png` | Citizen SOS Intake | `/help` | Citizen emergency intake form with English/Urdu bilingual support, speech-to-text voice reporting, emergency categorization, and GPS/landmark inputs. |
| `02-admin-dashboard.png` | Operator Dashboard | `/` | Emergency operations center overview displaying active incident counters, priority metrics, and the real-time priority queue. |
| `03-incident-detail-ai-analysis.png` | AI Analysis & Dispatch | `/incidents/[id]` | Incident triage view showcasing Google Gemini AI analysis via Strands Agent, distance calculation, structured resource recommendation, and the human-approval gate. |
| `04-live-coordination-map.png` | Emergency Map | `/` / `/incidents` | Interactive Leaflet/CARTO map rendering real-time incident pins, deployed rescue team markers, and corridor availability. |
| `05-adaptive-rescue-plans.png` | Adaptive Rescue Plans | `/plans` | Versioned rescue plan comparison interface showing context diffing, route obstruction triggers, and replanning proposals. |
| `06-resource-inventory.png` | Resource Inventory | `/resources` | Live inventory of emergency teams (Medical, Rescue, Fire, Shelter, Supplies) with status indicators, equipment, and active assignments. |
| `07-edge-gateway-sync.png` | Edge Gateway Console | Operator Console | Offline SOS packet queue manager demonstrating durable local storage and idempotent cloud synchronization. |

> **Note for Contributors:** Save screenshots directly to this folder matching the exact filenames listed above. High-DPI PNGs (1080p minimum) without browser chrome are recommended.
