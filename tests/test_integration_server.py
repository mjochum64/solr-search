#!/usr/bin/env python3
"""
Integration tests for the MCP Solr server using a real Solr instance.

These tests connect to a running Solr server and test the actual
functionality of the MCP server with real Solr queries.
"""
import os
import json
import pytest
import asyncio
from typing import Dict, Any
import httpx

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

# Import the server module
import server


@pytest.fixture
def solr_client():
    """Create a real SolrClient instance for integration testing."""
    return server.SolrClient(
        base_url="http://localhost:8983/solr",
        collection="documents"
    )


class MockRequestContext:
    """Mock context for integration testing."""
    
    def __init__(self, lifespan_context):
        """Initialize the mock context with the provided lifespan context."""
        self.lifespan_context = lifespan_context


class MockContext:
    """Mock MCP context for integration testing."""
    
    def __init__(self, request_context):
        """Initialize the mock context with the provided request context."""
        self.request_context = request_context


@pytest.fixture
def integration_context(solr_client):
    """Create a mock context with real Solr client for integration testing."""
    request_context = MockRequestContext({"solr_client": solr_client})
    return MockContext(request_context)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_solr_integration(integration_context):
    """Test the search_solr function with a real Solr server."""
    # Skip if Solr is not available
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8983/solr/documents/admin/ping")
            response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError):
        pytest.skip("Solr server not available")

    # Test a simple search
    result = await server.search_solr(integration_context, "Apache")
    parsed_result = json.loads(result)
    
    # Verify result structure
    assert "responseHeader" in parsed_result
    assert "response" in parsed_result
    assert parsed_result["responseHeader"]["status"] == 0
    
    # Verify that we got at least one result
    assert parsed_result["response"]["numFound"] >= 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_tool_integration(integration_context):
    """Test the search tool with a real Solr server."""
    # Skip if Solr is not available
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8983/solr/documents/admin/ping")
            response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError):
        pytest.skip("Solr server not available")

    # Test with filter and sorting
    params = {
        "query": "programming",
        "filter_query": "category:programming",
        "sort": "id asc",
        "rows": 3,
        "start": 0
    }
    
    result = await server.search(integration_context, params)
    
    # Verify result structure
    assert "responseHeader" in result
    assert "response" in result
    assert result["responseHeader"]["status"] == 0
    
    # Verify that we got filtered results
    assert result["response"]["numFound"] >= 1
    for doc in result["response"]["docs"]:
        assert doc["category"] == "programming"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_document_tool_integration(integration_context):
    """Test the get_document tool with a real Solr server."""
    # Skip if Solr is not available
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8983/solr/documents/admin/ping")
            response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError):
        pytest.skip("Solr server not available")

    # Test retrieving a specific document
    params = {
        "id": "doc1",
        "fields": ["title", "author"]
    }
    
    result = await server.get_document(integration_context, params)
    
    # Verify we got the correct document
    assert result["id"] == "doc1"
    assert "title" in result
    assert "author" in result
    assert "content" not in result  # Should not be included due to fields filter


@pytest.mark.asyncio
@pytest.mark.integration
async def test_solr_client_search_integration(solr_client):
    """Test the SolrClient search method with a real Solr server."""
    # Skip if Solr is not available
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8983/solr/documents/admin/ping")
            response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError):
        pytest.skip("Solr server not available")

    # Test basic search
    result = await solr_client.search(
        query="*:*",  # Match all documents
        rows=5
    )
    
    # Verify result structure
    assert "responseHeader" in result
    assert "response" in result
    assert result["responseHeader"]["status"] == 0
    assert result["response"]["numFound"] >= 5


@pytest.mark.asyncio
@pytest.mark.integration
async def test_error_handling_integration(solr_client):
    """Test error handling with a real Solr server."""
    # Skip if Solr is not available
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8983/solr/documents/admin/ping")
            response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError):
        pytest.skip("Solr server not available")

    # Test invalid query syntax
    with pytest.raises(httpx.HTTPStatusError):
        await solr_client.search(
            query="title:[* TO"  # Invalid syntax
        )

    # Test non-existent document
    result = await solr_client.get_document(
        doc_id="non_existent_document_id"
    )
    
    # Should return an error message
    assert "error" in result