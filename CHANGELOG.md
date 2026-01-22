# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1](https://github.com/fulviofreitas/eero-api/compare/v2.0.0...v2.0.1) (2026-01-22)

### 🐛 Bug Fixes

* trigger patch release ([808c2b1](https://github.com/fulviofreitas/eero-api/commit/808c2b1fcccb0953f27e113ca0ee5cccaad2f42f))

## [2.0.0](https://github.com/fulviofreitas/eero-api/compare/v1.4.3...v2.0.0) (2026-01-22)

### ⚠ BREAKING CHANGES

* raw response architecture (v2.0.0)

### ✨ Features

* raw response architecture (v2.0.0) ([2df19c8](https://github.com/fulviofreitas/eero-api/commit/2df19c823032b5ddc555530c39a2dad14d49ad26))

### 📚 Documentation

* add important notes about unofficial status and Amazon login limitation ([def3a40](https://github.com/fulviofreitas/eero-api/commit/def3a40b3ad7bd655ff364c9e5d368cf0baef437))

## [2.0.0](https://github.com/fulviofreitas/eero-api/compare/v1.4.3...v2.0.0) (2026-01-22)

### ⚠️ BREAKING CHANGES

This is a major breaking release that fundamentally changes how the library returns data.

* **All API methods now return raw JSON responses** from the Eero Cloud API without any transformation
* **Pydantic models removed** - The `models/` directory has been deleted; downstream clients must handle their own data transformation
* **No data extraction** - Response envelopes (`{"meta": {...}, "data": {...}}`) are returned as-is
* **No field renaming** - Raw field names like `wan_ip` are preserved (previously renamed to `public_ip`)
* **No status normalization** - Status values returned exactly as received from API

### 🔄 Migration Required

All downstream clients must update their code to:
1. Extract data from the `{"meta": {...}, "data": {...}}` envelope
2. Handle raw field names (e.g., `wan_ip` instead of `public_ip`)
3. Implement their own data transformation/normalization

See [MIGRATION.md](MIGRATION.md) for detailed upgrade instructions.

### ✨ Features

* **raw responses:** all endpoints return unmodified Eero Cloud API responses
* **passthrough architecture:** library now focuses on HTTP transport and authentication only

### 🗑️ Removed

* `src/eero/models/` - All Pydantic models (Network, Device, Eero, Profile, Account, Activity, Diagnostics)
* Data extraction logic from all API methods
* Field renaming/mapping in all API methods
* Status normalization (EeroNetworkStatus, EeroDeviceStatus enums removed from exports)
* Fallback data creation on errors

### 📚 Documentation

* Added MIGRATION.md with comprehensive upgrade guide
* Updated README.md with raw response examples

## [1.4.3](https://github.com/fulviofreitas/eero-api/compare/v1.4.2...v1.4.3) (2026-01-21)

### 🐛 Bug Fixes

* **api:** handle all HTTP 2xx status codes as success responses ([7b57787](https://github.com/fulviofreitas/eero-api/commit/7b57787db973dcdd63c30ee089464a9c866f26f3))

## [1.4.2](https://github.com/fulviofreitas/eero-api/compare/v1.4.1...v1.4.2) (2026-01-20)

### 🐛 Bug Fixes

* **ci:** use PR title only for squash merge to pass commitlint ([6b4747f](https://github.com/fulviofreitas/eero-api/commit/6b4747fc419131baa4930c1d181f6c0eecb07e71))

## [1.4.1](https://github.com/fulviofreitas/eero-api/compare/v1.4.0...v1.4.1) (2026-01-20)

### 🐛 Bug Fixes

* **security:** resolve credential disclosure in logs and add SecureLogger ([40f46a0](https://github.com/fulviofreitas/eero-api/commit/40f46a08cb6211518917e608d0c16cb5febca948))

## [1.4.0](https://github.com/fulviofreitas/eero-api/compare/v1.3.1...v1.4.0) (2026-01-20)

### ✨ Features

* add device pause and profile device management APIs ([023733c](https://github.com/fulviofreitas/eero-api/commit/023733c2a161ff9ff491c69836914c38e3e349ca))

## [1.3.1](https://github.com/fulviofreitas/eero-api/compare/v1.3.0...v1.3.1) (2026-01-19)

### 🐛 Bug Fixes

* detect actual version change in semantic-release action ([5d2f1ab](https://github.com/fulviofreitas/eero-api/commit/5d2f1ab6b5dc68c684ab0ed3e19d08d897122db9))

### 📚 Documentation

* add uv installation method to README ([0b11d85](https://github.com/fulviofreitas/eero-api/commit/0b11d85085e8edfcbf533ee68a9a0f509e3c8021))

## [1.3.0](https://github.com/fulviofreitas/eero-api/compare/v1.2.6...v1.3.0) (2026-01-19)

### ✨ Features

* release v1.3.0 ([c8f760b](https://github.com/fulviofreitas/eero-api/commit/c8f760bdc46cdf676c0eaede98ca613c8356684d))

### 🐛 Bug Fixes

* **ci:** remove invalid workflows permission from auto-merge ([d0cc06a](https://github.com/fulviofreitas/eero-api/commit/d0cc06adf5601d5a3343f6c96a7fbe45daeeb9b5))

## [1.2.6](https://github.com/fulviofreitas/eero-api/compare/v1.2.5...v1.2.6) (2026-01-18)

### 🐛 Bug Fixes

* **ci:** use GitHub App for auto-merge to support workflow file changes ([96f7ed1](https://github.com/fulviofreitas/eero-api/commit/96f7ed1035104665fb78293c6dadf52980d9165a))

## [1.2.5](https://github.com/fulviofreitas/eero-api/compare/v1.2.4...v1.2.5) (2026-01-18)

### 🐛 Bug Fixes

* **ci:** add robust conditions to prevent publish on failed release ([dd9b482](https://github.com/fulviofreitas/eero-api/commit/dd9b482ccf3bf64a756d70c40e4a1970deab962d))

### 📚 Documentation

* update documentation with PyPI publishing information ([1ff0694](https://github.com/fulviofreitas/eero-api/commit/1ff06941c451bc6a9d9b758065dfb6b5953dfd90))

## [1.2.4](https://github.com/fulviofreitas/eero-api/compare/v1.2.3...v1.2.4) (2026-01-18)

### 🐛 Bug Fixes

* **ci:** inline pypi-publish steps to avoid composite action Docker issue ([a9d8eb2](https://github.com/fulviofreitas/eero-api/commit/a9d8eb20e43e91bafb86a8aa34c785f6ba86a9bb))

## [1.2.3](https://github.com/fulviofreitas/eero-api/compare/v1.2.2...v1.2.3) (2026-01-18)

### 🐛 Bug Fixes

* **ci:** run notify-downstream in parallel with publishing ([9d0e5cc](https://github.com/fulviofreitas/eero-api/commit/9d0e5cc64dfabdc2e86ab28b3cc3c2f5542de330))

## [1.2.2](https://github.com/fulviofreitas/eero-api/compare/v1.2.1...v1.2.2) (2026-01-18)

### 🐛 Bug Fixes

* **ci:** disable attestations and fix repository-url handling ([67e1c0c](https://github.com/fulviofreitas/eero-api/commit/67e1c0cd8c0e8154359696e702fd114bb9ba9f15))

## [1.2.1](https://github.com/fulviofreitas/eero-api/compare/v1.2.0...v1.2.1) (2026-01-18)

### 🐛 Bug Fixes

* **ci:** append dev0 suffix for TestPyPI versions ([752e77e](https://github.com/fulviofreitas/eero-api/commit/752e77ea77ec36446a9f7fdfe628ce528b62a17a))

## [1.2.0](https://github.com/fulviofreitas/eero-api/compare/v1.1.0...v1.2.0) (2026-01-18)

### ✨ Features

* **ci:** chain TestPyPI validation before PyPI publish ([2bb5b5b](https://github.com/fulviofreitas/eero-api/commit/2bb5b5b5173c80ffeb3d8a1b1eee2f3ac8b9a22b))

### ♻️ Refactoring

* **ci:** use matrix strategy for downstream notifications ([8b55db6](https://github.com/fulviofreitas/eero-api/commit/8b55db6abd88b79526b57fa221ac5150e2c9c621))

## [1.1.0](https://github.com/fulviofreitas/eero-api/compare/v1.0.0...v1.1.0) (2026-01-18)

### ✨ Features

* **ci:** add PyPI publishing with Trusted Publishing ([15504b7](https://github.com/fulviofreitas/eero-api/commit/15504b783c79fd98f7e24b917656313190635245))

## 1.0.0 (2026-01-18)

### ✨ Features

* initial release of eero-api ([4854f74](https://github.com/fulviofreitas/eero-api/commit/4854f74c9340f9174a47d151665bbef149378e8a))
