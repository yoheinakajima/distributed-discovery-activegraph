# Importer maintenance

One importer change was required before the four-snapshot calibration set passed: `site/content/relations.yml` is now optional for snapshots that predate the canonical registry. The fallback is schema-based empty registry data; it does not name commits, invent relationships, or modify source. No later calibration-specific changes were required. The importer was frozen after all four imports.
