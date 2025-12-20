"""Tests for SSE parser."""

from replane._sse import SSEParser, parse_sse_stream


class TestSSEParser:
    """Tests for incremental SSE parsing."""

    def test_simple_event(self):
        parser = SSEParser()
        events = list(parser.feed("event: message\ndata: hello\n\n"))
        assert len(events) == 1
        assert events[0].event == "message"
        assert events[0].data == "hello"

    def test_json_data(self):
        parser = SSEParser()
        events = list(parser.feed('event: init\ndata: {"key": "value"}\n\n'))
        assert len(events) == 1
        assert events[0].event == "init"
        assert events[0].data == {"key": "value"}

    def test_multiline_data(self):
        parser = SSEParser()
        events = list(parser.feed("data: line1\ndata: line2\ndata: line3\n\n"))
        assert len(events) == 1
        assert events[0].data == "line1\nline2\nline3"

    def test_incremental_parsing(self):
        parser = SSEParser()

        # Feed partial data
        events = list(parser.feed("event: test\n"))
        assert len(events) == 0

        events = list(parser.feed("data: partial"))
        assert len(events) == 0

        # Complete the event
        events = list(parser.feed("\n\n"))
        assert len(events) == 1
        assert events[0].event == "test"
        assert events[0].data == "partial"

    def test_comment_ignored(self):
        parser = SSEParser()
        events = list(parser.feed(": this is a comment\nevent: test\ndata: value\n\n"))
        assert len(events) == 1
        assert events[0].event == "test"

    def test_event_id(self):
        parser = SSEParser()
        events = list(parser.feed("id: 123\nevent: test\ndata: value\n\n"))
        assert len(events) == 1
        assert events[0].id == "123"

    def test_retry_field(self):
        parser = SSEParser()
        events = list(parser.feed("retry: 5000\nevent: test\ndata: value\n\n"))
        assert len(events) == 1
        assert events[0].retry == 5000

    def test_field_without_value(self):
        parser = SSEParser()
        events = list(parser.feed("event\ndata: test\n\n"))
        assert len(events) == 1
        assert events[0].event == ""

    def test_carriage_return_handling(self):
        parser = SSEParser()
        events = list(parser.feed("event: test\r\ndata: value\r\n\r\n"))
        assert len(events) == 1
        assert events[0].event == "test"
        assert events[0].data == "value"

    def test_multiple_events(self):
        parser = SSEParser()
        stream = "event: first\ndata: 1\n\nevent: second\ndata: 2\n\n"
        events = list(parser.feed(stream))
        assert len(events) == 2
        assert events[0].event == "first"
        assert events[0].data == 1
        assert events[1].event == "second"
        assert events[1].data == 2

    def test_leading_space_in_value_stripped(self):
        parser = SSEParser()
        events = list(parser.feed("data: hello world\n\n"))
        assert len(events) == 1
        assert events[0].data == "hello world"  # Leading space after : is stripped

    def test_multiple_leading_spaces_preserved(self):
        parser = SSEParser()
        # Only first space is stripped per SSE spec
        events = list(parser.feed("data:  two spaces\n\n"))
        assert len(events) == 1
        assert events[0].data == " two spaces"  # One space remains


class TestParseSSEStream:
    """Tests for the stream parsing helper."""

    def test_parses_chunks(self):
        chunks = ["event: a\ndata: 1\n", "\nevent: b\ndata: 2\n\n"]
        events = list(parse_sse_stream(iter(chunks)))
        assert len(events) == 2

    def test_empty_stream(self):
        events = list(parse_sse_stream(iter([])))
        assert len(events) == 0

    def test_incomplete_event_not_yielded(self):
        # Stream ends without completing the event
        chunks = ["event: incomplete\ndata: test"]
        events = list(parse_sse_stream(iter(chunks)))
        assert len(events) == 0
