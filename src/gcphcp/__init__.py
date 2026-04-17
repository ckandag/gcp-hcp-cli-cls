"""GCP HCP CLI - A command-line interface for Google Cloud Platform HCP.

This package provides a comprehensive CLI for managing clusters and nodepools
through the GCP HCP API, following gcloud CLI conventions.
"""

__version__ = "1.0.4"
__author__ = "Red Hat GCP HCP Team"
__email__ = "hcm-gcp-hcp@redhat.com"

from .cli.main import main

__all__ = ["main"]
