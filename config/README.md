# Configuration

This directory contains version-controlled configuration controlling the behaviour of the Pulse analytics project.

## Planned Configuration Format

Project and synthetic-data configuration will use TOML.

Python 3.12 includes the standard-library `tomllib` module for reading TOML files, so no additional configuration package is required.

## Intended Contents

Configuration may eventually include:

- simulation timeframe
- target dataset scale
- acquisition assumptions
- product-behaviour probabilities
- subscription parameters
- seasonality
- experiment settings
- controlled data-quality corruption rates

Values should be introduced deliberately during implementation rather than invented during repository setup.

## Secrets

Credentials and machine-specific secrets do not belong in this directory.

Those will be supplied locally through `.env` and represented safely using the repository's `.env.example` template.
