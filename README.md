# Config Size Guard (CSG) 🛡️

Config Size Guard (CSG) is an intelligent, multi-layer anomaly detection tool for configuration files. Designed to prevent catastrophic outages caused by configuration bloat, truncation, or structural drift, CSG acts as a crucial CI/CD safety net before broken configs can be propagated to production environments.

Inspired by real-world incidents (like the CrowdStrike Channel File 291 BSOD, Cloudflare's Bot Management regex bloat, and FAA's NOTAM database truncation), CSG analyzes configuration changes beyond simple syntax validation.

## 🌟 Key Features

* **Multi-Layer Analysis**:
  * **Layer 1 (Delta Growth)**: Compares current file size and key counts against your Git baseline (`HEAD~1`) to catch sudden spikes or drops.
  * **Layer 2 (Internal Consistency & Structure)**: Analyzes JSON/YAML/TOML structures for metadata-count mismatches (e.g. `total_rules: 150` but the array only has 72 items), hidden hard-limit breaches, and structural key inflation.
* **Format Agnostic but Smart**: Scans any text configuration (YAML, JSON, TOML, HCL, XML, etc.). For parseable formats like JSON/YAML, it performs deep structural consistency checks.
* **SIEM Ready**: Outputs results in standard formats or NDJSON for seamless integration with Splunk, Elasticsearch, or Logstash.
* **CI/CD Native**: Extremely lightweight and designed to fail your pipeline safely before disaster strikes.

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/FerryAchmadAkbar/config-size-guard.git
cd config-size-guard
pip install -e .
```

### Usage

Run CSG against your configuration directories:

```bash
csg check /path/to/configs --format text
```

To integrate with your Git workflow (compares against `HEAD~1`):

```bash
# In your project root
csg check .
```

Generate NDJSON for SIEM ingestion:

```bash
csg check . --format json > security_events.jsonl
```

## 🛠️ Configuration

CSG is fully customizable. You can define dynamic floors, warning thresholds, and IQR sensitivities via `csg.config.yaml` at your repository root.

```yaml
# csg.config.yaml
static_floor:
  size_warn_kb: 500
  size_fail_kb: 10240

growth:
  size_spike_ratio: 2.0
  size_drop_ratio: 0.1

keycount:
  item_key_inflation_threshold: 0.05
```

## 🧠 Why CSG? (The Postmortem Connection)

Syntax validators and linters only check if a configuration is *valid*. CSG checks if a configuration is *safe*. 
- **CrowdStrike Incident (2024)**: A valid file with 21 fields instead of 20 crashed millions of machines. CSG's structural inflation layer catches this.
- **Cloudflare (2025)**: A bot management feature file grew 6x due to a bad SQL query, causing severe memory spikes. CSG's growth ratio layer catches this.
- **FAA (2023)**: The NOTAM database was truncated, halting all US flights. CSG's internal consistency and delta drop layers catch this.

## 📝 License
MIT License. See `LICENSE` for more information.
