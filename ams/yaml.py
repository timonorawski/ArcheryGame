"""Unified YAML/JSON loader for AMS.

Provides a consistent interface for loading configuration files that works
across environments:
- Native Python: Uses PyYAML for .yaml files, json for .json files
- Browser/WASM: Falls back to JSON only (PyYAML not available)

Also provides optional JSON Schema validation via jsonschema library.

Usage:
    from ams.yaml import load, loads, dump, dumps, HAS_YAML

    # Load from file (auto-detects format from extension)
    data = load(Path('game.yaml'))
    data = load(Path('game.json'))

    # Load from string (specify format)
    data = loads(content, format='yaml')
    data = loads(content, format='json')

    # Load from file-like object
    with open('game.yaml') as f:
        data = load(f, format='yaml')

    # Load with schema validation
    data = load(Path('game.yaml'), schema=Path('game.schema.json'))

    # Validate data against schema
    validate(data, schema)

    # Dump to string
    yaml_str = dumps(data, format='yaml')
    json_str = dumps(data, format='json')

Environment variables:
    AMS_FORCE_JSON: If set, always use JSON even if YAML is available
    AMS_SKIP_SCHEMA_VALIDATION: If set, skip schema validation
"""

from pathlib import Path
from typing import Any, Dict, IO, Optional, Union
import json
import os

# PyYAML is optional - not available in browser/WASM builds
try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _yaml = None  # type: ignore
    _HAS_YAML = False

# jsonschema is optional - used for schema validation
try:
    import jsonschema as _jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:
    _jsonschema = None  # type: ignore
    _HAS_JSONSCHEMA = False

# Allow forcing JSON mode for testing
HAS_YAML = _HAS_YAML and not os.environ.get('AMS_FORCE_JSON')
HAS_JSONSCHEMA = _HAS_JSONSCHEMA

# Skip validation if environment variable is set
SKIP_VALIDATION = bool(os.environ.get('AMS_SKIP_SCHEMA_VALIDATION'))


class YAMLNotAvailableError(ImportError):
    """Raised when YAML loading is requested but PyYAML is not available."""

    def __init__(self, path: Optional[Union[str, Path]] = None):
        if path:
            msg = f"Cannot load {path}: PyYAML not available. Use JSON format for browser builds."
        else:
            msg = "PyYAML not available. Use JSON format for browser builds."
        super().__init__(msg)


def _detect_format(path: Union[str, Path]) -> str:
    """Detect file format from extension."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in ('.yaml', '.yml'):
        return 'yaml'
    elif suffix == '.json':
        return 'json'
    else:
        # Default to YAML if available, otherwise JSON
        return 'yaml' if HAS_YAML else 'json'


def load(
    source: Union[str, Path, IO[str]],
    format: Optional[str] = None,
) -> Any:
    """Load data from a file path or file-like object.

    Args:
        source: File path (str or Path) or file-like object
        format: 'yaml', 'json', or None to auto-detect from extension

    Returns:
        Parsed data (usually dict or list)

    Raises:
        YAMLNotAvailableError: If YAML format requested but PyYAML not available
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If JSON parsing fails
        yaml.YAMLError: If YAML parsing fails
    """
    # Handle file path
    if isinstance(source, (str, Path)):
        path = Path(source)
        if format is None:
            format = _detect_format(path)

        with open(path, 'r', encoding='utf-8') as f:
            return _load_from_file(f, format, path)

    # Handle file-like object
    if format is None:
        # Try to get name from file object
        name = getattr(source, 'name', None)
        format = _detect_format(name) if name else ('yaml' if HAS_YAML else 'json')

    return _load_from_file(source, format)


def _load_from_file(f: IO[str], format: str, path: Optional[Path] = None) -> Any:
    """Load from an open file object."""
    if format == 'yaml':
        if not HAS_YAML:
            raise YAMLNotAvailableError(path)
        return _yaml.safe_load(f)
    else:
        return json.load(f)


def loads(content: str, format: str = 'yaml') -> Any:
    """Load data from a string.

    Args:
        content: String content to parse
        format: 'yaml' or 'json'

    Returns:
        Parsed data (usually dict or list)

    Raises:
        YAMLNotAvailableError: If YAML format requested but PyYAML not available
    """
    if format == 'yaml':
        if not HAS_YAML:
            raise YAMLNotAvailableError()
        return _yaml.safe_load(content)
    else:
        return json.loads(content)


def dump(
    data: Any,
    dest: Union[str, Path, IO[str]],
    format: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Dump data to a file path or file-like object.

    Args:
        data: Data to serialize
        dest: File path (str or Path) or file-like object
        format: 'yaml', 'json', or None to auto-detect from extension
        **kwargs: Additional arguments passed to yaml.dump or json.dump

    Raises:
        YAMLNotAvailableError: If YAML format requested but PyYAML not available
    """
    # Handle file path
    if isinstance(dest, (str, Path)):
        path = Path(dest)
        if format is None:
            format = _detect_format(path)

        with open(path, 'w', encoding='utf-8') as f:
            _dump_to_file(data, f, format, **kwargs)
        return

    # Handle file-like object
    if format is None:
        name = getattr(dest, 'name', None)
        format = _detect_format(name) if name else 'json'

    _dump_to_file(data, dest, format, **kwargs)


def _dump_to_file(data: Any, f: IO[str], format: str, **kwargs: Any) -> None:
    """Dump to an open file object."""
    if format == 'yaml':
        if not HAS_YAML:
            raise YAMLNotAvailableError()
        # Default to readable YAML output
        kwargs.setdefault('default_flow_style', False)
        kwargs.setdefault('allow_unicode', True)
        _yaml.dump(data, f, **kwargs)
    else:
        # Default to readable JSON output
        kwargs.setdefault('indent', 2)
        kwargs.setdefault('ensure_ascii', False)
        json.dump(data, f, **kwargs)


def dumps(data: Any, format: str = 'yaml', **kwargs: Any) -> str:
    """Dump data to a string.

    Args:
        data: Data to serialize
        format: 'yaml' or 'json'
        **kwargs: Additional arguments passed to yaml.dump or json.dumps

    Returns:
        Serialized string

    Raises:
        YAMLNotAvailableError: If YAML format requested but PyYAML not available
    """
    if format == 'yaml':
        if not HAS_YAML:
            raise YAMLNotAvailableError()
        kwargs.setdefault('default_flow_style', False)
        kwargs.setdefault('allow_unicode', True)
        return _yaml.dump(data, **kwargs)
    else:
        kwargs.setdefault('indent', 2)
        kwargs.setdefault('ensure_ascii', False)
        return json.dumps(data, **kwargs)


def safe_load(content: str) -> Any:
    """Alias for loads(content, format='yaml') for compatibility.

    Raises YAMLNotAvailableError if PyYAML is not available.
    """
    return loads(content, format='yaml')


def safe_load_path(path: Union[str, Path]) -> Any:
    """Load YAML from a file path, with auto-detection.

    This is a convenience function that:
    - Loads .yaml/.yml files as YAML (if available)
    - Loads .json files as JSON
    - Falls back to JSON if YAML not available

    Args:
        path: Path to file

    Returns:
        Parsed data
    """
    return load(path)


# =============================================================================
# Schema Validation
# =============================================================================

class SchemaValidationError(Exception):
    """Raised when data fails schema validation."""

    def __init__(self, message: str, errors: Optional[list] = None, path: Optional[Path] = None):
        self.errors = errors or []
        self.path = path
        super().__init__(message)


def load_schema(schema_source: Union[str, Path, Dict]) -> Dict:
    """Load a JSON schema from file path or dict.

    Args:
        schema_source: Path to schema file, or schema dict

    Returns:
        Schema dict
    """
    if isinstance(schema_source, dict):
        return schema_source

    path = Path(schema_source)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate(
    data: Any,
    schema: Union[str, Path, Dict],
    raise_on_error: bool = True,
) -> Optional[list]:
    """Validate data against a JSON schema.

    Args:
        data: Data to validate
        schema: Schema dict, or path to schema file
        raise_on_error: If True, raise SchemaValidationError on failure

    Returns:
        None if valid, or list of error messages if raise_on_error=False

    Raises:
        SchemaValidationError: If validation fails and raise_on_error=True
    """
    if SKIP_VALIDATION:
        return None

    if not HAS_JSONSCHEMA:
        # Silently skip validation if jsonschema not available
        return None

    schema_dict = load_schema(schema)

    try:
        _jsonschema.validate(data, schema_dict)
        return None
    except _jsonschema.ValidationError as e:
        errors = [str(e.message)]

        # Collect all errors if using Draft7Validator
        try:
            validator = _jsonschema.Draft7Validator(schema_dict)
            errors = [err.message for err in validator.iter_errors(data)]
        except Exception:
            pass

        if raise_on_error:
            raise SchemaValidationError(
                f"Schema validation failed: {errors[0]}",
                errors=errors
            )
        return errors


def load_and_validate(
    source: Union[str, Path],
    schema: Union[str, Path, Dict],
    format: Optional[str] = None,
) -> Any:
    """Load data and validate against schema in one step.

    Args:
        source: File path to load
        schema: Schema dict, or path to schema file
        format: 'yaml', 'json', or None to auto-detect

    Returns:
        Parsed and validated data

    Raises:
        YAMLNotAvailableError: If YAML format requested but not available
        SchemaValidationError: If validation fails
    """
    data = load(source, format=format)

    path = Path(source) if isinstance(source, (str, Path)) else None
    errors = validate(data, schema, raise_on_error=False)

    if errors:
        raise SchemaValidationError(
            f"Schema validation failed for {path or 'data'}: {errors[0]}",
            errors=errors,
            path=path
        )

    return data
