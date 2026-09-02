# Plugin Development Guide

Telegram AI OS treats optional capabilities as plugins. Core Telegram ingestion, security, persistence, and mode safeguards remain stable while plugins subscribe to application events.

## Contract

A plugin subclasses `BasePlugin` and exposes immutable `PluginMetadata`. Register it during composition, not from Telegram handlers. `PluginManager` validates unique IDs, resolves plugin dependency order, initializes/shuts down plugins, and subscribes/unsubscribes handlers through the Event Bus.

## Rules

- A plugin must not import Telegram webhook handlers to execute business logic.
- A plugin must request explicit capabilities through metadata permissions.
- Sensitive Telegram actions must go through application services and permission policies.
- Plugin configuration belongs in `plugin_settings` or environment-backed settings, never hard-coded secrets.
- Plugin failures must not terminate the core event path.
- Database schema changes require an Alembic revision.
- Add unit tests before enabling a plugin in production.
