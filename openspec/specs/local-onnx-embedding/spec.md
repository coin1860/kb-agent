# Capability: Local ONNX Embedding

## Purpose

Provides the capability to use locally stored ONNX embedding models for ChromaDB vector operations, enabling fully offline deployment without internet access or heavy PyTorch dependencies.

## Requirements

### Requirement: Support Local ONNX Embedding Models
The system SHALL provide the capability to load and use local ONNX embedding models for ChromaDB vector operations, (specifically RoBERTa-based architectures like BGE-M3, explicitly supporting 8K context dimensions, dynamically filtering supported ONNX inputs, extracting the CLS token instead of Mean Pooling, and favoring Cosine Similarity metrics), ensuring functionality in fully offline environments without requiring internet access or heavy PyTorch dependencies.

#### Scenario: System runs in an offline environment with a local model
- **WHEN** the `KB_AGENT_EMBEDDING_MODEL_PATH` environment variable or corresponding configuration is set to a valid local directory containing an ONNX model (e.g., BGE-M3)
- **AND** `KB_AGENT_EMBEDDING_URL` is not set
- **THEN** the system SHALL initialize ChromaDB using a custom ONNX embedding function pointing to the specified local model, dynamically detecting valid ONNX node inputs, and explicitly applying M2-optimized CPU thread constraints
- **AND** the target Chroma collection SHALL be forcefully initialized using the `cosine` distance space
- **AND** document indexing and retrieval operations SHALL function normally using the local ONNX model by extracting the CLS token rather than processing a mean pooled token aggregate

#### Scenario: Fallback to default ChromaDB model
- **WHEN** neither `KB_AGENT_EMBEDDING_URL` nor `KB_AGENT_EMBEDDING_MODEL_PATH` are configured
- **THEN** the system SHALL fall back to ChromaDB's default embedding function
