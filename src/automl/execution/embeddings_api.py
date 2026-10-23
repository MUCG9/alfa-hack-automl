"""Dormant typed CPU backend; default workers/registry remain unchanged."""
from automl.contracts.embeddings import EmbeddingRequest,EmbeddingResult


def fit_predict_embeddings(request:EmbeddingRequest,train,test)->EmbeddingResult:
    from automl.execution.model_adapters.embeddings import fit_predict
    return fit_predict(request,train,test)
