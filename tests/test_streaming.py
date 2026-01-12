"""Tests for streaming chat functionality."""

import pytest

from src.agent import ShippingAgent
from src.agent.agent import StreamEvent


@pytest.fixture
def mock_agent():
    """Create a mock mode agent."""
    return ShippingAgent()


class TestMockModeStreaming:
    """Tests for streaming in mock mode."""

    @pytest.mark.asyncio
    async def test_stream_yields_text_and_complete(self, mock_agent):
        """Streaming should yield text and complete events."""
        events: list[StreamEvent] = []
        async for event in mock_agent.chat_stream("hello"):
            events.append(event)

        assert len(events) >= 2
        # Should have at least one text event and one complete event
        types = [e.get("type") for e in events]
        assert "text" in types
        assert "complete" in types

    @pytest.mark.asyncio
    async def test_stream_text_contains_response(self, mock_agent):
        """Text events should contain the response content."""
        text_content = ""
        async for event in mock_agent.chat_stream("hello"):
            if event.get("type") == "text":
                text_content += event.get("content", "")

        # Should have non-empty text
        assert len(text_content) > 0

    @pytest.mark.asyncio
    async def test_stream_complete_is_last(self, mock_agent):
        """Complete event should be the last event."""
        events: list[StreamEvent] = []
        async for event in mock_agent.chat_stream("hello"):
            events.append(event)

        assert events[-1].get("type") == "complete"

    @pytest.mark.asyncio
    async def test_stream_rate_request(self, mock_agent):
        """Rate request should yield text with rates info."""
        text_content = ""
        async for event in mock_agent.chat_stream("get rates to LA for 2lb package"):
            if event.get("type") == "text":
                text_content += event.get("content", "")

        # Should include rate information
        assert "USPS" in text_content or "UPS" in text_content or "FedEx" in text_content

    @pytest.mark.asyncio
    async def test_stream_preserves_conversation_state(self, mock_agent):
        """Streaming should preserve conversation state for follow-ups."""
        # First, get rates
        async for _ in mock_agent.chat_stream("get rates to Seattle WA 98101 for 2lb"):
            pass

        # Then ask about shipping
        text_content = ""
        async for event in mock_agent.chat_stream("ship it"):
            if event.get("type") == "text":
                text_content += event.get("content", "")

        # Should have created a shipment or at least reference shipping
        assert len(text_content) > 0


class TestStreamEventTypes:
    """Tests for stream event structure."""

    @pytest.mark.asyncio
    async def test_text_event_has_content(self, mock_agent):
        """Text events should have content field."""
        async for event in mock_agent.chat_stream("hello"):
            if event.get("type") == "text":
                assert "content" in event
                break

    @pytest.mark.asyncio
    async def test_complete_event_structure(self, mock_agent):
        """Complete events should have proper structure."""
        async for event in mock_agent.chat_stream("hello"):
            if event.get("type") == "complete":
                assert event.get("type") == "complete"
                # content should be empty string for complete
                assert event.get("content", "") == ""


class TestStreamValidation:
    """Tests for streaming input validation."""

    @pytest.mark.asyncio
    async def test_stream_handles_address_validation(self, mock_agent):
        """Should handle address validation in stream."""
        text_content = ""
        async for event in mock_agent.chat_stream("validate 123 Main St, Los Angeles CA 90001"):
            if event.get("type") == "text":
                text_content += event.get("content", "")

        # Should mention validation
        assert "valid" in text_content.lower() or "address" in text_content.lower()

    @pytest.mark.asyncio
    async def test_stream_handles_tracking(self, mock_agent):
        """Should handle tracking requests in stream."""
        text_content = ""
        async for event in mock_agent.chat_stream("track order 1234"):
            if event.get("type") == "text":
                text_content += event.get("content", "")

        # Should have tracking information
        assert len(text_content) > 0
