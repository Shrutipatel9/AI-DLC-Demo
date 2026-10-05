"""Platform module: configuration, database, logging, errors and vendor ports.

The platform never imports feature modules (identity, health). Feature modules
depend on the platform ports, and the app factory wires concrete adapters in.
"""
