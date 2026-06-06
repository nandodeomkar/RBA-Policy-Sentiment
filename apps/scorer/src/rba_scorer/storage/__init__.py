"""Readers/writers for the data/ contract (JSON, CSV) and on-disk caches.

Named `storage` rather than `io` (as sketched in the design) to avoid shadowing
the standard-library `io` module within the package namespace.
"""
