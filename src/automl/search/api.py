"""Public boundary for opt-in research advice, with no default runner changes."""
def request_advice(request,*,enabled=False):
    from automl.search.assistants import propose
    return propose(request,enabled=enabled)
