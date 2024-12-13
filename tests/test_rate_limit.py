"""
Tests for rate limiting functionality in LLMPRTypeCategoryAnalyzerPlugin.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock
from openai import AsyncOpenAI

from analyzers.plugins.category_analyzer import LLMPRTypeCategoryAnalyzerPlugin


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    return Mock(spec=AsyncOpenAI)


@pytest.fixture
def mock_encoding():
    """Create a mock encoding."""
    encoding = Mock()
    encoding.encode.return_value = [1] * 10  # Each text will count as 10 tokens
    return encoding


@pytest.fixture
def rate_limiter(mock_openai_client, mock_encoding):
    """Create a rate limiter instance with test settings."""
    plugin = LLMPRTypeCategoryAnalyzerPlugin(
        mock_openai_client, mock_encoding, 10, 50, 1, ""
    )
    return plugin


@pytest.mark.asyncio
async def test_rate_limit_requests(rate_limiter):
    """Test that requests are properly rate limited."""
    start_time = time.monotonic()

    # Make max_requests requests
    for _ in range(rate_limiter.max_requests):
        await rate_limiter._rate_limit(5)  # 5 tokens per request

    # The next request should be delayed
    await rate_limiter._rate_limit(5)

    elapsed_time = time.monotonic() - start_time
    assert (
        elapsed_time >= rate_limiter.period
    ), "Rate limit was not enforced for requests"


@pytest.mark.asyncio
async def test_rate_limit_tokens(rate_limiter):
    """Test that token usage is properly rate limited."""
    start_time = time.monotonic()

    # Use up the token limit (50 tokens) with 5 requests of 10 tokens each
    for _ in range(5):
        await rate_limiter._rate_limit(10)

    # The next request should be delayed
    await rate_limiter._rate_limit(10)

    elapsed_time = time.monotonic() - start_time
    assert elapsed_time >= rate_limiter.period, "Rate limit was not enforced for tokens"


@pytest.mark.asyncio
async def test_rate_limit_cleanup(rate_limiter):
    """Test that old entries are properly cleaned up."""
    # Fill up the queues
    for _ in range(5):
        await rate_limiter._rate_limit(5)

    initial_length = len(rate_limiter.request_times)

    # Wait for period to expire
    await asyncio.sleep(rate_limiter.period + 0.1)

    # Make a new request to trigger cleanup
    await rate_limiter._rate_limit(5)

    assert (
        len(rate_limiter.request_times) < initial_length
    ), "Old entries were not cleaned up"
    assert len(rate_limiter.request_times) == len(
        rate_limiter.token_counts
    ), "Request times and token counts are out of sync"


@pytest.mark.asyncio
async def test_rate_limit_concurrent(rate_limiter):
    """Test rate limiting with concurrent requests."""

    async def make_request(token_count: int):
        await rate_limiter._rate_limit(token_count)
        return time.monotonic()

    # Launch 20 concurrent requests
    start_time = time.monotonic()
    tasks = [make_request(5) for _ in range(20)]
    completion_times = await asyncio.gather(*tasks)

    # Check that requests were spread across at least 2 periods
    time_span = max(completion_times) - start_time
    assert (
        time_span >= rate_limiter.period
    ), "Concurrent requests were not properly rate limited"

    # Check that we didn't exceed our limits at any point
    assert (
        len(rate_limiter.request_times) <= rate_limiter.max_requests
    ), "Request limit was exceeded"
    assert (
        sum(rate_limiter.token_counts) <= rate_limiter.max_tokens
    ), "Token limit was exceeded"


@pytest.mark.asyncio
async def test_rate_limit_mixed_token_sizes(rate_limiter):
    """Test rate limiting with varying token counts."""
    start_time = time.monotonic()

    # Send requests with different token counts
    token_counts = [5, 15, 25, 5]  # Total: 50 tokens
    for tokens in token_counts:
        await rate_limiter._rate_limit(tokens)

    # This request should be delayed as we've hit the token limit
    await rate_limiter._rate_limit(10)

    elapsed_time = time.monotonic() - start_time
    assert (
        elapsed_time >= rate_limiter.period
    ), "Token-based rate limit was not enforced for mixed token sizes"
