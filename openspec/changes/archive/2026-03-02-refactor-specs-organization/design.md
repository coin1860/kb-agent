# Design: Refactor OpenSpec Specs Organization

## Domain Mapping

| Domain | Components |
|:---|:---|
| **ingestion** | index-command, indexing-pipeline, semantic-chunking |
| **retrieval** | hybrid-retrieval, parallel-retrieval, vector-search-threshold |
| **routing** | adaptive-query-routing, fast-path-classifier, query-engine |
| **synthesis** | corrective-rag, local-file-qa-tool, rag-synthesis |
| **guard** | planner-tool-guard, security-masking |
| **obs** | llm-usage-tracking |

## Implementation Details

### Directory Renames
```bash
mv openspec/specs/index-command openspec/specs/ingestion-index-command
mv openspec/specs/indexing-pipeline openspec/specs/ingestion-indexing-pipeline
mv openspec/specs/semantic-chunking openspec/specs/ingestion-semantic-chunking
# ... and so on
```

### Metadata Updates
Each `spec.md` will include:
```yaml
domain: <domain>
```
in its frontmatter.
