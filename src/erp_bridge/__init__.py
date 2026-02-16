"""
ERP Bridge - CSV to Tally via MCP
Accepts invoice data via CSV, validates, converts to Tally XML, and uploads.

This module is fully isolated from the existing GST Scanner pipeline.
It does not import from any existing src/ modules.
"""

__version__ = "0.1.0"
