---
name: notion
description: Notion API — create/read pages and databases via curl
triggers: [notion, nota, note, page, database, block, apuntes, documento]
requires: {bins: [curl], env: [NOTION_API_KEY]}
emoji: 📝
source: builtin
---
# Notion Skill

Uses Notion REST API via curl. Requires NOTION_API_KEY env var.

## Setup
```
$env:NOTION_API_KEY = "ntn_your_key_here"
```
Or set permanently: `setx NOTION_API_KEY "ntn_your_key_here"`

## Search pages
```
curl -X POST "https://api.notion.com/v1/search" `
  -H "Authorization: Bearer $env:NOTION_API_KEY" `
  -H "Notion-Version: 2022-06-28" `
  -H "Content-Type: application/json" `
  -d '{"query":"<search term>"}'
```

## Read a page
```
curl "https://api.notion.com/v1/pages/<page_id>" `
  -H "Authorization: Bearer $env:NOTION_API_KEY" `
  -H "Notion-Version: 2022-06-28"
```

## Create a page
```
curl -X POST "https://api.notion.com/v1/pages" `
  -H "Authorization: Bearer $env:NOTION_API_KEY" `
  -H "Notion-Version: 2022-06-28" `
  -H "Content-Type: application/json" `
  -d '{"parent":{"page_id":"<parent_id>"},"properties":{"title":{"title":[{"text":{"content":"<title>"}}]}}}'
```

## Tips
- Run via run_powershell (PowerShell handles backtick line continuation)
- Page IDs come from the URL: notion.so/page-title-<id>
- Always check NOTION_API_KEY is set before running
