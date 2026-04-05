## Context
The current indexing pipeline fetches content from various sources, converts it, and writes them to local `.md` files. It then uses an LLM to generate a full document summary. Finally, it embeds both the extracted standalone summary as one document, and standard Markdown chunk separations as other documents. 

Problems:
1. Documents from local sources are redundantly written during indexing instead of being processed directly from memory.
2. Generating a full document summary for all documents indiscriminately is computationally expensive, slow, and unnecessary for short snippets.
3. Standalone summary embeddings don't directly feed contextual content into RAG queries appropriately since context mapping isn't tightly coupled. Small document chunks (as little as 10-20 characters) currently lose context when split and indexed individually.

## Goals / Non-Goals

**Goals:**
- Eliminate redundant file I/O when processing existing `.md` datasets.
- Save LLM inference cost by skipping document summaries for documents under 2000 characters.
- Ensure all chunks maintain contextual awareness by injecting context (e.g., document title, section title, summary) into the string sent for vector embedding.
- Eliminate independent, discrete `-summary` indexing records in ChromaDB.

**Non-Goals:**
- Moving to a new embedding model, altering the dimension constraints, or ripping out ChromaDB.
- Modifying the Connector classes which pull data, which function fine independently.

## Decisions

- **Direct Chunk Contextualization**: Rather than maintaining a separate chunk for the document summary, prepend contextual markers directly to the payload of textual chunks before storing in ChromaDB. The string format `Document: {title}\nSection: {section_title}\n\n{original_text}` naturally feeds high-fidelity contextual constraints through vector search. 
  - *Alternatives considered*: Modifying the metadata scheme and the subsequent retrieval `nodes.py` to recreate context manually. The prefixing strategy limits complexity and improves semantic proximity instantly.
- **Conditional Summarization**: Only use the LLM to generate a document summary if the raw document length exceeds 2000 characters. Shorter documents are fundamentally easy to parse during standard vector search and chunking.
- **Drop Index Side-effect Writing**: Stop redundantly invoking `f.write()` within `Processor.process` to create `.md` cached files unless absolutely necessary (for instance, when indexing from a web connector). Prioritize processing straight from memory strings to avoid slowing indexing with disk interactions.

## Risks / Trade-offs

- **[Risk] Prepending strings into chunk contents increases chunk token widths**: Prepending metadata to small chunks might pollute semantic distances and shift vector clusters.
  - *Mitigation*: Keep prefix syntax extremely succinct.
- **[Risk] Schema Inconsistency**: The new format clashes dramatically with the existing Chroma index, where `doc_id-summary` was distinctly indexed.
  - *Mitigation*: Enforce a persistent datastore clearing as part of project deployment after this change applies, instructing users to delete the `.chroma` directory and re-ingest.
