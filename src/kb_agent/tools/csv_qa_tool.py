import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

import pandas as pd

from kb_agent.config import settings

logger = logging.getLogger(__name__)

# Global cache for DataFrames
_df_cache: Dict[str, pd.DataFrame] = {}


def clear_cache() -> None:
    """Clear the pandas DataFrame cache to free memory."""
    global _df_cache
    _df_cache.clear()
    logger.debug("CSV cache cleared.")


def _find_csv_file(filename: str) -> Optional[str]:
    """
    Search for the given CSV file in archive/ then source/ directories.
    Returns the absolute path if found, otherwise None.
    """
    if not filename.endswith(".csv"):
        filename += ".csv"
    
    base_dir = Path(settings.data_folder)
    
    # Priority 1: archive folder
    archive_path = base_dir / "archive" / filename
    if archive_path.exists():
        return str(archive_path)
        
    # Priority 3: input folder
    input_path = base_dir / "input" / filename
    if input_path.exists():
        return str(input_path)
        
    return None


def get_csv_schema_and_sample(filename: str) -> str:
    """
    Get the schema (columns and dtypes) and a small sample of the CSV.
    This helps the LLM write accurate queries.
    """
    file_path = _find_csv_file(filename)
    if not file_path:
        return f"Error: CSV file '{filename}' not found in archive or source folders."
        
    try:
        # Load into cache if not present
        if file_path not in _df_cache:
            _df_cache[file_path] = pd.read_csv(file_path)
            
        df = _df_cache[file_path]
        
        # Build schema representation
        schema_info = []
        for col, dtype in df.dtypes.items():
            schema_info.append(f"- {col} ({dtype})")
            
        schema_str = "\n".join(schema_info)
        sample_str = df.head(3).to_markdown()
        
        return f"Schema:\n{schema_str}\n\nSample Data (first 3 rows):\n{sample_str}"
        
    except Exception as e:
        return f"Error reading CSV {filename}: {str(e)}"


def csv_query(filename: str, query_json_str: str) -> str:
    """
    Query a CSV file using a structured JSON containing 'condition' and 'columns'.
    
    Args:
        filename: Name of the CSV file to query (e.g. 'dataset.csv')
        query_json_str: JSON string containing the query parameters.
            Format: {"condition": "Age > 30 and Department == 'Sales'", "columns": ["Name", "Salary"]}
            - condition: Pandas query string. Keep empty or null to skip filtering.
            - columns: List of columns to return. Keep empty or null to return all columns.
            
    Returns:
        Markdown table of the results, up to 50 rows.
    """
    file_path = _find_csv_file(filename)
    if not file_path:
        return f"Error: CSV file '{filename}' not found in archive or source folders."
        
    try:
        # Parse the JSON query
        try:
            query_obj = json.loads(query_json_str)
        except json.JSONDecodeError as e:
            return f"Error parsing query JSON: {str(e)}. Please provide a valid JSON string."
            
        condition = query_obj.get("condition")
        columns = query_obj.get("columns")
        
        # Load into cache if not present
        if file_path not in _df_cache:
            _df_cache[file_path] = pd.read_csv(file_path)
            
        df = _df_cache[file_path]
        
        result_df = df
        
        # Apply filter condition if provided
        if condition and str(condition).strip():
            try:
                result_df = result_df.query(condition)
            except Exception as e:
                headers = list(df.columns)
                return (
                    f"Error executing condition '{condition}': {str(e)}.\n"
                    f"CRITICAL: Do not generate the same erroneous query again. "
                    f"The valid column headers in the CSV are: {headers}. "
                    f"Please correct your pandas query strictly using ONLY these headers and try again."
                )
                
        # Select columns if provided
        if columns and isinstance(columns, list) and len(columns) > 0:
            try:
                # Ensure all columns exist
                missing_cols = [col for col in columns if col not in result_df.columns]
                if missing_cols:
                    return f"Error: the following requested columns do not exist in the DataFrame: {missing_cols}. Available columns are: {list(result_df.columns)}"
                    
                result_df = result_df[columns]
            except Exception as e:
                return f"Error selecting columns {columns}: {str(e)}."
                
        # Limit the results and convert to markdown
        limited_df = result_df.head(50)
        
        if limited_df.empty:
            return "Query returned no results."
            
        return limited_df.to_markdown(index=False)
        
    except Exception as e:
        return f"Unexpected error executing query on {filename}: {str(e)}"

