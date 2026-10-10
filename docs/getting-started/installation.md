# Installation

There is no published YANTRA package or repository packaging configuration at present. Do not run an assumed `pip install` or claim a package name is available. The proposed packaging direction is Python 3.12+, uv for development and dependency management, and hatchling as build backend.

Future installation documentation must state supported Python versions, extras and optional dependencies, provider-specific dependencies, artifact provenance, and a tested clean-environment command. A release gate requires reproducible wheels/sdists and installation tests from the built artifact.
