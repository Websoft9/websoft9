from io import StringIO
import re

from dotenv.parser import parse_stream

from src.core.exception import CustomException


def format_env_assignment(key: str, value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")
        .replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    )
    return f'{key}="{escaped}"\n'


def parse_env_values(content: str) -> dict[str, str]:
    values = {}
    for binding in parse_stream(StringIO(content)):
        if binding.error:
            raise CustomException(
                400, "Invalid Request",
                f"Invalid environment assignment at line {binding.original.line}.",
            )
        if binding.key is None or binding.value is None:
            continue
        value = binding.value
        raw_value = binding.original.string.partition("=")[2].lstrip()
        if raw_value.startswith("'"):
            quoted = re.match(r"'((?:\\.|[^'\\])*)'", raw_value, re.DOTALL)
            if quoted is None:
                raise CustomException(
                    400, "Invalid Request",
                    f"Invalid environment assignment at line {binding.original.line}.",
                )
            # Compose preserves backslashes in single-quoted values.
            value = quoted.group(1).replace("\\'", "'")
        elif raw_value.startswith('"'):
            value = value.replace("$$", "$")
        values[binding.key] = value
    return values
