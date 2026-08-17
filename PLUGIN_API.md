# Plugin API Specification — Loopix Extension System

## Overview

Loopix plugins implement standard extension interfaces (`LanguageProvider`, `ModelProvider`, `ToolProvider`, `ContextProvider`) and pass through `PermissionEngine` security authorization.

## Plugin Manifest Schema

```json
{
  "name": "my-custom-plugin",
  "version": "1.0.0",
  "description": "Custom language provider extension",
  "capabilities": ["language_parsing"],
  "permissions_required": ["read_file"],
  "dependencies": []
}
```
