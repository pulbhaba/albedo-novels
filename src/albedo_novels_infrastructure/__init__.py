"""Adapters that wrap third-party SDKs and provide concrete ports.

This package is the only place that may import SDK code (FastAPI, boto3,
PyJWT, SQLAlchemy, ...). It is imported by both `albedo_novels_lambda` and
`albedo_novels_local` through the composition module.
"""
