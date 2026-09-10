# 🔗 Ecosystem

Projects built on top of the `eero-api` SDK, and where this library sits among them.

---

## 📐 Where the SDK Sits

`eero-api` is the transport layer and nothing more. Since v2.0.0 it returns the Eero Cloud API's
responses unmodified — every consumer owns its own data extraction, presentation, and storage.

```
              ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐
              │   eeroctl    │  │   eero-ui    │  │ eero-prometheus-exporter │
              │     (CLI)    │  │  (dashboard) │  │        (metrics)         │
              └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘
                     └─────────────────┼───────────────────────┘
                                       │
                              ┌────────▼─────────┐
                              │     eero-api     │  ← this project
                              │  (raw JSON SDK)  │
                              └────────┬─────────┘
                                       │ HTTPS
                              ┌────────▼─────────┐
                              │ api-user.e2ro.com│
                              └──────────────────┘
```

> **Note**: If you are looking for a finished tool rather than a library, start with
> [eeroctl](https://github.com/fulviofreitas/eeroctl). Reach for the SDK when you are
> building something of your own.

---

## 🛠️ First-Party Projects

| Project | What it is |
|---------|------------|
| **[🖥️ eeroctl](https://github.com/fulviofreitas/eeroctl)** | Terminal interface for Eero networks. This is where all CLI commands (`eero auth login`, `eero network list`, …) live — they are **not** part of this SDK |
| **[🛜 eero-ui](https://github.com/fulviofreitas/eero-ui)** | Svelte dashboard for network management |
| **[📊 eero-prometheus-exporter](https://github.com/fulviofreitas/eero-prometheus-exporter)** | Prometheus metrics for monitoring Eero networks |

---

## 🌱 Used By

Community projects that depend on `eero-api`:

| Project | Description |
|---------|-------------|
| **[eero-dashboard](https://github.com/xrvk/eero-dashboard)** | Self-hosted React + FastAPI dashboard for Eero mesh networks |
| **[eero-cli](https://github.com/lidless-labs/eero-cli)** | Tiny CLI for non-interactive SMS auth, device listing, and bulk block |
| **[py-bandwith-monitor](https://github.com/awongCM/py-bandwith-monitor)** | Python bandwidth monitor with an optional Eero-backed data source |
| **[assorted](https://github.com/jss367/assorted/tree/master/network_debug/check_eero_routers)** | Personal Eero router debug and inspection scripts |

> 💡 **Tip:** Building something on top of `eero-api`? Open a PR against
> [README.md](https://github.com/fulviofreitas/eero-api/blob/master/README.md) to get listed.

---

## 🧩 Building Your Own Consumer

A few things the existing consumers learned the hard way:

- **Own your schema.** Responses are raw and the upstream API is undocumented and unversioned in
  practice. Define your own [TypedDicts or models](Raw-Response-Format#typing-guidance) at your
  application boundary so an upstream field rename breaks in one place.
- **Respect the rate ceiling.** Roughly 100 requests/minute across the account. Tune
  `cache_timeout` rather than adding sleeps — see
  [Caching and Rate Limits](Caching-and-Rate-Limits).
- **Do not persist preferences in the SDK.** It deliberately stores credentials only. Preference
  storage moved out to the CLI in v4.0.0; your project should own its own config.
- **Pin the version.** Major releases have carried real breaking changes — see
  [Migration](Migration).

---

## 🙏 Lineage

This project is a modern revamp of the original
[eero-client](https://github.com/343max/eero-client) by
[@343max](https://github.com/343max), and was previously published under that name.

---

## 🔗 Related Pages

- [Home](Home) — Overview and quick start
- [Python API](Python-API) — Full guide to `EeroClient`
- [Raw Response Format](Raw-Response-Format) — Why consumers own data extraction
- [Caching and Rate Limits](Caching-and-Rate-Limits) — Staying under the request ceiling
- [Contributing](Contributing) — Development setup for this repository
