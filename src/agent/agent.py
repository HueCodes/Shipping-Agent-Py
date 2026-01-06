"""Shipping agent powered by Claude."""

from __future__ import annotations

import logging
import os
from typing import Any, TYPE_CHECKING

from .context import CustomerContext
from .tools import TOOLS, ToolExecutor

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Token estimation: ~4 chars per token
CHARS_PER_TOKEN = 4
MAX_CONVERSATION_TOKENS = 50000
SUMMARIZE_THRESHOLD_TOKENS = 50000
KEEP_RECENT_TURNS = 5

SYSTEM_PROMPT_TEMPLATE = """You are a shipping assistant for {store_name}. You help the merchant manage their shipping operations through natural conversation.

You have access to tools for:
- Viewing unfulfilled orders
- Getting shipping rates from multiple carriers
- Validating addresses
- Creating shipments and labels
- Tracking packages
- Bulk shipping operations

Guidelines:
- Always confirm before purchasing labels (spending money)
- Proactively validate addresses before shipping
- When showing rates, highlight the best value option
- For bulk operations, summarize what will happen and confirm
- If an address has issues, explain and suggest corrections

{context}"""


def is_mock_mode() -> bool:
    """Check if mock mode is enabled."""
    return os.getenv("MOCK_MODE", "").lower() in ("1", "true", "yes")


class ShippingAgent:
    """Claude-powered shipping agent with tool calling."""

    def __init__(
        self,
        context: CustomerContext | None = None,
        db: Session | None = None,
    ):
        self.mock_mode = is_mock_mode()
        self.messages: list[dict] = []
        self.context = context or CustomerContext.default()
        self.db = db
        self._token_count = 0

        # Database conversation persistence
        self.conversation_repo = None
        self.conversation_id = None
        if db is not None and self.context.customer_id:
            from src.db.repository import ConversationRepository
            self.conversation_repo = ConversationRepository(db)
            conversation = self.conversation_repo.get_or_create(self.context.customer_id)
            self.conversation_id = conversation.id
            # Load existing messages
            self.messages = self.conversation_repo.get_messages(conversation.id)
            if self.messages:
                logger.info("Loaded %d messages from conversation history", len(self.messages))

        # Cache for mock mode conversation state
        self._last_city: str | None = None
        self._last_state: str | None = None
        self._last_zip: str | None = None
        self._last_weight: float | None = None

        if self.mock_mode:
            from src.mock import MockEasyPostClient
            self.easypost = MockEasyPostClient()
            self.client = None  # No Claude client needed in mock mode
        else:
            import anthropic
            from src.easypost_client import EasyPostClient

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set. Use MOCK_MODE=1 to test without API keys.")

            self.client = anthropic.Anthropic(api_key=api_key)
            self.easypost = EasyPostClient()

        self.executor = ToolExecutor(self.easypost, context=self.context, db=db)

    @property
    def system_prompt(self) -> str:
        """Generate system prompt with context."""
        return SYSTEM_PROMPT_TEMPLATE.format(
            store_name=self.context.store_name,
            context=self.context.format_for_prompt(),
        )

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text length."""
        return len(text) // CHARS_PER_TOKEN

    def _estimate_message_tokens(self, message: dict) -> int:
        """Estimate tokens in a message."""
        content = message.get("content", "")
        if isinstance(content, str):
            return self._estimate_tokens(content)
        elif isinstance(content, list):
            total = 0
            for block in content:
                if isinstance(block, dict):
                    total += self._estimate_tokens(str(block))
                else:
                    # Anthropic content block object
                    total += self._estimate_tokens(str(block))
            return total
        return 0

    def _estimate_conversation_tokens(self) -> int:
        """Estimate total tokens in conversation."""
        total = self._estimate_tokens(self.system_prompt)
        for msg in self.messages:
            total += self._estimate_message_tokens(msg)
        return total

    def _summarize_old_messages(self) -> None:
        """Summarize older messages when conversation exceeds token limit."""
        if len(self.messages) <= KEEP_RECENT_TURNS * 2:
            return  # Not enough messages to summarize

        # Split into old and recent
        recent_start = len(self.messages) - (KEEP_RECENT_TURNS * 2)
        old_messages = self.messages[:recent_start]
        recent_messages = self.messages[recent_start:]

        # Build summary of old conversation
        summary_parts = ["Previous conversation summary:"]
        for msg in old_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                # Truncate long content
                if len(content) > 200:
                    content = content[:200] + "..."
                summary_parts.append(f"- {role}: {content}")
            elif isinstance(content, list):
                # Summarize tool calls/results
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_result":
                            result = block.get("content", "")[:100]
                            summary_parts.append(f"- tool result: {result}...")
                        elif block.get("type") == "tool_use":
                            summary_parts.append(f"- tool call: {block.get('name', 'unknown')}")

        summary = "\n".join(summary_parts)

        # Replace old messages with summary
        self.messages = [
            {"role": "user", "content": f"[Conversation context]\n{summary}"},
            {"role": "assistant", "content": "I understand. Let me continue helping you with your shipping needs."},
            *recent_messages,
        ]
        logger.info(
            "Summarized conversation: %d messages -> %d messages",
            len(old_messages) + len(recent_messages),
            len(self.messages),
        )

    def _maybe_summarize(self) -> None:
        """Check if summarization is needed and perform it."""
        tokens = self._estimate_conversation_tokens()
        self._token_count = tokens
        if tokens > SUMMARIZE_THRESHOLD_TOKENS:
            logger.info("Conversation exceeds %d tokens, summarizing...", SUMMARIZE_THRESHOLD_TOKENS)
            self._summarize_old_messages()

    def can_create_label(self) -> bool:
        """Check if current context allows creating a label."""
        return self.context.can_create_labels(1)

    def chat(self, user_message: str) -> str:
        """Send a message and get a response, handling tool calls."""
        if self.mock_mode:
            return self._mock_chat(user_message)

        return self._real_chat(user_message)

    def _persist_messages(self, user_message: str, assistant_response: str) -> None:
        """Persist user and assistant messages to database."""
        if self.conversation_repo and self.conversation_id:
            self.conversation_repo.append_message(
                self.conversation_id,
                {"role": "user", "content": user_message},
            )
            self.conversation_repo.append_message(
                self.conversation_id,
                {"role": "assistant", "content": assistant_response},
            )

    def _mock_chat(self, user_message: str) -> str:
        """Handle chat in mock mode - uses parsing + tool execution."""
        from src.mock import get_mock_response
        from src.parser import parse_shipping_input, describe_parsed

        lower = user_message.lower()
        parsed = parse_shipping_input(user_message)

        # Cache parsed info for follow-up commands
        if parsed.city:
            self._last_city = parsed.city
        if parsed.state:
            self._last_state = parsed.state
        if parsed.zip_code:
            self._last_zip = parsed.zip_code
        if parsed.weight_oz:
            self._last_weight = parsed.weight_oz

        # Detect intent and execute appropriate tool
        if any(word in lower for word in ["rate", "cost", "price", "how much", "ship to"]):
            # Build params from parsed input
            params = {
                "to_city": parsed.city or "Los Angeles",
                "to_state": parsed.state or "CA",
                "to_zip": parsed.zip_code or "90001",
                "weight_oz": parsed.weight_oz or 32,
            }

            result = self.executor.execute("get_shipping_rates", params)

            # Show what we parsed
            parsed_desc = describe_parsed(parsed)
            response = f"**Shipping**: {parsed_desc}\n\n{result}"

            if not parsed.has_destination:
                response += "\n\n*Note: Using default destination (LA). Specify a city, state, or ZIP for accurate rates.*"
            if not parsed.has_weight:
                response += "\n\n*Note: Using default weight (2 lbs). Specify weight for accurate rates.*"

            response += "\n\nWould you like me to ship with any of these options?"
            self._persist_messages(user_message, response)
            return response

        elif any(word in lower for word in ["valid", "check", "verify"]):
            params = {
                "name": "Recipient",
                "street": "123 Main St",
                "city": parsed.city or "Los Angeles",
                "state": parsed.state or "CA",
                "zip": parsed.zip_code or "90001",
            }
            result = self.executor.execute("validate_address", params)
            self._persist_messages(user_message, result)
            return result

        elif any(word in lower for word in ["ship it", "create", "buy", "use the"]):
            # Get the first cached rate_id (cheapest) if available
            cached_rate_ids = list(self.executor._last_rates.keys())
            if not cached_rate_ids:
                result = "No rates in cache. Please get shipping rates first by saying something like 'get rates to LA for 2lb package'."
                self._persist_messages(user_message, result)
                return result

            rate_id = cached_rate_ids[0]  # Use cheapest (first) rate

            params = {
                "to_name": "Recipient",
                "to_street": "123 Main St",
                "to_city": self._last_city or parsed.city or "Los Angeles",
                "to_state": self._last_state or parsed.state or "CA",
                "to_zip": self._last_zip or parsed.zip_code or "90001",
                "weight_oz": self._last_weight or parsed.weight_oz or 32,
                "rate_id": rate_id,
            }
            result = self.executor.execute("create_shipment", params)
            self._persist_messages(user_message, result)
            return result

        elif any(word in lower for word in ["track", "where is", "status"]):
            # Extract tracking number or order id
            import re
            tracking_match = re.search(r'\b(1Z\d{9}|94\d{9}|78\d{9})\b', user_message)
            order_match = re.search(r'(ORD-\d+|#?\d{4,})', user_message)

            params = {}
            if tracking_match:
                params["tracking_number"] = tracking_match.group(1)
            elif order_match:
                order_id = order_match.group(1)
                if order_id.startswith("#"):
                    order_id = f"ORD-{order_id[1:]}"
                elif not order_id.startswith("ORD-"):
                    order_id = f"ORD-{order_id}"
                params["order_id"] = order_id
            else:
                result = "Please provide a tracking number or order ID to track."
                self._persist_messages(user_message, result)
                return result

            result = self.executor.execute("get_tracking_status", params)
            self._persist_messages(user_message, result)
            return result

        elif any(word in lower for word in ["bulk", "ship all", "batch"]):
            # Parse bulk shipping intent
            params: dict = {"cheapest": True}

            if "under 1 lb" in lower or "under 1lb" in lower or "under 16 oz" in lower:
                params["filter"] = {"max_weight_oz": 16}
            elif "california" in lower or " ca" in lower:
                params["filter"] = {"destination_state": "CA"}

            # Check for confirmation
            if "yes" in lower or "confirm" in lower or "proceed" in lower:
                params["confirmed"] = True

            result = self.executor.execute("bulk_ship_orders", params)
            self._persist_messages(user_message, result)
            return result

        elif any(word in lower for word in ["order", "unfulfilled", "pending", "need to ship"]):
            params = {"limit": 20}
            # Check for search terms
            if "california" in lower or " ca" in lower:
                params["search"] = "CA"
            elif "texas" in lower or " tx" in lower:
                params["search"] = "TX"
            result = self.executor.execute("get_unfulfilled_orders", params)
            self._persist_messages(user_message, result)
            return result

        else:
            result = get_mock_response(user_message)
            self._persist_messages(user_message, result)
            return result

    def _real_chat(self, user_message: str) -> str:
        """Handle chat with real Claude API."""
        import anthropic

        self.messages.append({"role": "user", "content": user_message})

        # Check if we need to summarize old messages
        self._maybe_summarize()

        try:
            while True:
                try:
                    response = self.client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1024,
                        system=self.system_prompt,
                        tools=TOOLS,
                        messages=self.messages,
                        timeout=60.0,  # 60 second timeout for API calls
                    )
                except anthropic.RateLimitError as e:
                    logger.error("Anthropic rate limit exceeded: %s", e)
                    return "I'm currently experiencing high demand. Please try again in a moment."
                except anthropic.APIStatusError as e:
                    logger.error("Anthropic API error: %s", e)
                    return f"I encountered an API error: {e.message}. Please try again."
                except anthropic.APITimeoutError as e:
                    logger.error("Anthropic API timeout: %s", e)
                    return "The request timed out. Please try again with a simpler request."
                except anthropic.APIConnectionError as e:
                    logger.error("Anthropic connection error: %s", e)
                    return "I'm having trouble connecting to the AI service. Please check your connection."

                # Check if we need to handle tool calls
                if response.stop_reason == "tool_use":
                    # Process tool calls
                    assistant_content = response.content
                    self.messages.append({"role": "assistant", "content": assistant_content})

                    # Execute each tool call with error handling
                    tool_results = []
                    for block in assistant_content:
                        if block.type == "tool_use":
                            try:
                                result = self.executor.execute(block.name, block.input)
                            except Exception as e:
                                logger.error(
                                    "Tool execution failed for '%s': %s. Input: %s",
                                    block.name, e, block.input
                                )
                                result = f"Error: Tool '{block.name}' failed: {e}"
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            })

                    self.messages.append({"role": "user", "content": tool_results})
                    # Continue the loop to get Claude's response to the tool results

                else:
                    # No more tool calls, return the final response
                    self.messages.append({"role": "assistant", "content": response.content})

                    # Extract text from response
                    text_parts = []
                    for block in response.content:
                        if hasattr(block, "text"):
                            text_parts.append(block.text)

                    final_response = "\n".join(text_parts)

                    # Persist to database - sync conversation messages
                    if self.conversation_repo and self.conversation_id:
                        # Convert messages to serializable format
                        serializable_messages = []
                        for msg in self.messages:
                            content = msg.get("content", "")
                            if isinstance(content, list):
                                # Convert Anthropic content blocks to dicts
                                content = [
                                    dict(b) if hasattr(b, "__dict__") else b
                                    for b in content
                                ]
                            serializable_messages.append({
                                "role": msg["role"],
                                "content": content,
                            })
                        self.conversation_repo.set_messages(self.conversation_id, serializable_messages)

                    return final_response

        except Exception as e:
            logger.error("Unexpected error in chat: %s", e, exc_info=True)
            return f"An unexpected error occurred: {e}. Please try again."

    def reset(self) -> None:
        """Clear conversation history."""
        self.messages = []
        self._token_count = 0

        # Clear database conversation if available
        if self.conversation_repo and self.conversation_id:
            self.conversation_repo.clear_messages(self.conversation_id)
