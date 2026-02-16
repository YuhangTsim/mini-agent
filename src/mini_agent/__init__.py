"""Mini Agent - Dual framework AI platform.

Usage:
    from mini_agent import roo, open
    
    # Use roo-agent (mode-based)
    agent = roo.Agent(mode="coder")
    
    # Use open-agent (multi-agent)
    session = open.Session()
"""

__version__ = "2.0.0"

# Lazy imports for performance
def __getattr__(name):
    if name == "roo":
        import roo_agent as _roo
        return _roo
    elif name == "open":
        import open_agent as _open
        return _open
    raise AttributeError(f"module 'mini_agent' has no attribute '{name}'")
