"""Tests for pilab.scout.filter — topic keyword matching."""

from pilab.scout.filter import match_topics


def test_match_ai_keyword():
    topics = match_topics("New LLM quantization technique")
    assert "ai" in topics


def test_match_telco():
    topics = match_topics("O-RAN alliance announces new 5G spec")
    assert "telco" in topics


def test_match_fintech():
    topics = match_topics("Open banking API for embedded finance")
    assert "fintech" in topics


def test_match_edge():
    topics = match_topics("Running TinyML on Raspberry Pi")
    assert "edge" in topics


def test_no_match():
    topics = match_topics("Cooking recipes for dinner tonight")
    assert topics == []


def test_case_insensitive():
    topics = match_topics("New LLM from Huggingface released today")
    assert "ai" in topics


def test_multiple_topics():
    topics = match_topics("llm inference on raspberry pi with 5g mec")
    assert "ai" in topics
    assert "edge" in topics
    assert "telco" in topics
