# Capability: Local ONNX Embedding

## Purpose

Provides the capability to use locally stored ONNX embedding models for ChromaDB vector operations, enabling fully offline deployment without internet access or heavy PyTorch dependencies.

## Requirements

### Requirement: Support Local ONNX Embedding Models
The system SHALL provide the capability to load and use local ONNX embedding models for ChromaDB vector operations, ensuring functionality in fully offline environments without requiring internet access or heavy PyTorch dependencies.

#### Scenario: System runs in an offline environment with a local model
- **WHEN** the `KB_AGENT_EMBEDDING_MODEL_PATH` environment variable or corresponding configuration is set to a valid local directory containing an ONNX model
- **AND** `KB_AGENT_EMBEDDING_URL` is not set
- **THEN** the system SHALL initialize ChromaDB using a custom ONNX embedding function pointing to the specified local model
- **AND** document indexing and retrieval operations SHALL function normally using the local ONNX model

#### Scenario: Fallback to default ChromaDB model
- **WHEN** neither `KB_AGENT_EMBEDDING_URL` nor `KB_AGENT_EMBEDDING_MODEL_PATH` are configured
- **THEN** the system SHALL fall back to ChromaDB's default embedding function
