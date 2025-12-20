"""Server-Sent Events (SSE) parser for the Replane Python SDK.

This module provides SSE parsing utilities that work with both sync and async
HTTP responses. SSE is used for real-time config updates from the Replane server.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterator


@dataclass
class SSEEvent:
    """A parsed Server-Sent Event.

    Attributes:
        event: Event type (e.g., "init", "config_change").
        data: Parsed JSON data from the event.
        id: Optional event ID.
        retry: Optional retry interval in milliseconds.
    """

    event: str | None
    data: Any
    id: str | None = None
    retry: int | None = None


class SSEParser:
    """Incremental SSE parser that handles partial data.

    This parser accumulates data and yields complete events as they
    become available. It handles multi-line data fields and the SSE
    protocol format.

    Example:
        parser = SSEParser()
        for chunk in response.iter_bytes():
            for event in parser.feed(chunk.decode()):
                print(f"Event: {event.event}, Data: {event.data}")
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._event_type: str | None = None
        self._data_lines: list[str] = []
        self._event_id: str | None = None
        self._retry: int | None = None

    def feed(self, chunk: str) -> Iterator[SSEEvent]:
        """Feed a chunk of data to the parser and yield complete events.

        Args:
            chunk: A string chunk from the SSE stream.

        Yields:
            SSEEvent objects for each complete event in the chunk.
        """
        self._buffer += chunk

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)

            # Remove optional carriage return
            if line.endswith("\r"):
                line = line[:-1]

            # Empty line signals end of event
            if not line:
                if self._data_lines:
                    yield self._emit_event()
                continue

            # Skip comments
            if line.startswith(":"):
                continue

            # Parse field
            if ":" in line:
                field, _, value = line.partition(":")
                # Remove single leading space from value if present
                if value.startswith(" "):
                    value = value[1:]
            else:
                field = line
                value = ""

            match field:
                case "event":
                    self._event_type = value
                case "data":
                    self._data_lines.append(value)
                case "id":
                    self._event_id = value
                case "retry":
                    try:
                        self._retry = int(value)
                    except ValueError:
                        pass

    def _emit_event(self) -> SSEEvent:
        """Create an SSEEvent from accumulated data and reset state."""
        data_str = "\n".join(self._data_lines)

        # Try to parse as JSON
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            data = data_str

        event = SSEEvent(
            event=self._event_type,
            data=data,
            id=self._event_id,
            retry=self._retry,
        )

        # Reset for next event
        self._event_type = None
        self._data_lines = []
        # Note: id and retry persist across events per SSE spec

        return event


def parse_sse_stream(chunks: Iterator[str]) -> Iterator[SSEEvent]:
    """Parse an SSE stream from string chunks.

    This is a convenience function for sync HTTP responses.

    Args:
        chunks: Iterator of string chunks from the response.

    Yields:
        SSEEvent objects as they are parsed.
    """
    parser = SSEParser()
    for chunk in chunks:
        yield from parser.feed(chunk)


async def parse_sse_stream_async(chunks: AsyncIterator[str]) -> AsyncIterator[SSEEvent]:
    """Parse an SSE stream from async string chunks.

    This is a convenience function for async HTTP responses.

    Args:
        chunks: Async iterator of string chunks from the response.

    Yields:
        SSEEvent objects as they are parsed.
    """
    parser = SSEParser()
    async for chunk in chunks:
        for event in parser.feed(chunk):
            yield event
