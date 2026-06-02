# Collector Overview

The collector:

- loads active config from MySQL
- maintains OPC sessions per enabled machine
- applies exponential backoff per failed machine
- reads tags in configurable OPC chunks
- writes samples to SQLite first
- flushes SQLite to MySQL in bounded batches
- updates machine/tag status tables
- reloads config without API restart
- exits cleanly for restart commands

Environment variables controlling collector behavior are documented in `.env.example`.
