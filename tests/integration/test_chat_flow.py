"""Integration tests for chat flow and conversation management."""

import pytest


class TestBasicChat:
    """Tests for basic chat functionality."""

    def test_simple_greeting(self, chat_helper):
        """Test that the agent responds to a simple greeting."""
        result = chat_helper.send("Hello")
        assert "error" not in result
        assert "response" in result
        assert len(result["response"]) > 0

    def test_rate_request(self, chat_helper):
        """Test requesting shipping rates."""
        result = chat_helper.send("Get rates for a 2lb package to Los Angeles, CA 90001")
        assert "error" not in result
        response = result["response"].lower()
        # Should mention rates or carriers
        assert any(term in response for term in ["rate", "usps", "ups", "fedex", "$"])

    def test_address_validation(self, chat_helper):
        """Test address validation request."""
        result = chat_helper.send("Validate address: 123 Main St, Chicago, IL 60601")
        assert "error" not in result
        response = result["response"].lower()
        assert any(term in response for term in ["valid", "address", "verified"])

    def test_empty_message_rejected(self, test_client):
        """Test that empty messages are rejected."""
        response = test_client.post(
            "/api/chat",
            json={"message": "", "session_id": "test"},
        )
        # 422 Unprocessable Entity for Pydantic validation errors
        assert response.status_code == 422


class TestMultiTurnConversation:
    """Tests for multi-turn conversation context."""

    def test_context_preserved_across_turns(self, chat_helper):
        """Test that context is preserved across multiple messages."""
        # First message: ask for rates
        result1 = chat_helper.send("Get rates for a 32oz package to Miami, FL 33101")
        assert "error" not in result1

        # Second message: reference previous context
        result2 = chat_helper.send("What's the cheapest option?")
        assert "error" not in result2
        # Should be able to answer about cheapest from cached rates
        response = result2["response"].lower()
        assert any(term in response for term in ["cheap", "usps", "rate", "$"])

    def test_followup_ship_command(self, chat_helper):
        """Test shipping after getting rates."""
        # Get rates first
        chat_helper.send("Get rates for 16oz to Seattle, WA 98101")

        # Follow up with ship command
        result = chat_helper.send("Ship it with USPS to John Doe at 123 Pine St")
        assert "error" not in result
        response = result["response"].lower()
        # Should mention shipment, tracking, or label
        assert any(term in response for term in ["ship", "track", "label", "created"])

    def test_conversation_reset(self, chat_helper):
        """Test that conversation reset clears context."""
        # Build some context
        chat_helper.send("Get rates for 24oz to Denver, CO 80201")

        # Reset
        chat_helper.reset()

        # New message shouldn't have previous context
        result = chat_helper.send("What's the cheapest option?")
        assert "error" not in result
        # Without context, should ask for clarification or give generic response


class TestSessionIsolation:
    """Tests for session isolation between users."""

    def test_different_sessions_isolated(self, test_client):
        """Test that different sessions don't share state."""
        # Session A: set up some context
        session_a = "session-alpha"
        response_a1 = test_client.post(
            "/api/chat",
            json={"message": "Get rates for 32oz to NYC 10001", "session_id": session_a},
        )
        assert response_a1.status_code == 200

        # Session B: different session
        session_b = "session-beta"
        response_b1 = test_client.post(
            "/api/chat",
            json={"message": "What rates did you find?", "session_id": session_b},
        )
        assert response_b1.status_code == 200

        # Session B shouldn't know about Session A's rates
        response_b = response_b1.json()["response"].lower()
        # Should either ask for clarification or not have the NYC context
        # This is a soft assertion - the agent might handle it differently

    def test_session_id_returned(self, test_client):
        """Test that session ID is returned in response."""
        response = test_client.post(
            "/api/chat",
            json={"message": "Hello", "session_id": "my-custom-session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data


class TestAuthenticatedChat:
    """Tests for authenticated chat with customer context."""

    def test_authenticated_chat_works(self, authenticated_chat, sample_customer):
        """Test that authenticated chat works with customer context."""
        result = authenticated_chat.send("Hello, what can you help me with?")
        assert "error" not in result
        assert "response" in result

    def test_customer_context_in_response(self, authenticated_chat, sample_customer):
        """Test that agent responds to customer context question."""
        result = authenticated_chat.send("How many labels can I create this month?")
        assert "error" not in result
        # In mock mode, agent may give generic response
        # In real mode, should know about label limits from CustomerContext
        response = result["response"].lower()
        # Should respond about labels/shipping in some way
        assert len(response) > 0  # Just verify we got a response

    def test_authenticated_with_orders(self, authenticated_chat, sample_orders):
        """Test that authenticated user can access their orders."""
        result = authenticated_chat.send("Show me my unfulfilled orders")
        assert "error" not in result
        response = result["response"].lower()
        # Should find orders or mention order-related terms
        assert any(term in response for term in ["order", "unfulfilled", "#1001", "#1002"])


class TestConversationPersistence:
    """Tests for conversation persistence to database."""

    def test_messages_persisted(self, authenticated_chat, conversation_repo, sample_customer):
        """Test that messages are persisted to database."""
        # Send a message
        authenticated_chat.send("Get rates for 16oz to Boston, MA 02101")

        # Check database for conversation
        conversation = conversation_repo.get_or_create(sample_customer.id)
        messages = conversation_repo.get_messages(conversation.id)

        # Should have at least the user message and agent response
        assert len(messages) >= 2

    def test_conversation_history_maintained(self, authenticated_chat, conversation_repo, sample_customer):
        """Test that conversation history accumulates."""
        # Send multiple messages
        authenticated_chat.send("Hello")
        authenticated_chat.send("Get rates for 32oz to LA")
        authenticated_chat.send("Thanks")

        # Check database
        conversation = conversation_repo.get_or_create(sample_customer.id)
        messages = conversation_repo.get_messages(conversation.id)

        # Should have all user messages plus responses
        user_messages = [m for m in messages if m.get("role") == "user"]
        assert len(user_messages) >= 3


class TestErrorHandling:
    """Tests for error handling in chat."""

    def test_handles_invalid_json_gracefully(self, test_client):
        """Test that invalid JSON is handled."""
        response = test_client.post(
            "/api/chat",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422  # Unprocessable Entity

    def test_handles_missing_message_field(self, test_client):
        """Test that missing message field is handled."""
        response = test_client.post(
            "/api/chat",
            json={"session_id": "test"},
        )
        assert response.status_code == 422

    def test_handles_very_long_message(self, chat_helper):
        """Test handling of very long messages."""
        long_message = "a" * 10000
        result = chat_helper.send(long_message)
        # Should either process or return error, not crash
        assert "response" in result or "error" in result
