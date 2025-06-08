# Shiro Backend

This repository contains the backend implementation for **Shiro**, an AI-powered assistant built during a generative AI-themed hackathon. The backend is built using FastAPI and supports modular orchestration of agent workflows via Composio’s Model Context Protocol (MCP).

## Overview

**Shiro** is an intelligent assistant that can access and execute tasks across platforms such as Gmail, Notion, Slack, WhatsApp, and Google Calendar — all through a single conversational interface. The assistant is context-aware and capable of handling multi-step workflows through hierarchical agents.

### Example Query:
> Send a message to "abc@gmail.com" explaining the recipe for pancakes.

Shiro would automatically construct the message, seek confirmation if needed, and use the appropriate API (e.g., Gmail MCP integration) to execute the action.

## Problem Statement and Value Proposition

While the hackathon theme was broad ("Generative AI"), we focused on practical enterprise use-cases:

- **Increased productivity**: By integrating multiple services into a single conversational interface, Shiro eliminates the need to switch between tools.
- **Reduced recruitment/training time**: Companies often spend time onboarding new employees onto internal tools. A customized version of Shiro could act as a productivity layer over these tools, drastically reducing the learning curve.
- **Fewer manual errors**: Automating workflows reduces the chance of mistakes often caused by repetitive manual tasks.

## Technical Architecture

The backend leverages:

- **FastAPI** for REST API implementation
- **MCP (Model Context Protocol)** for service integration
- **Streaming and Non-Streaming** response modes via Server-Sent Events (SSE)
- **Hierarchical agent routing** for task delegation
- **Modular agent configuration** for services like Gmail, Slack, Notion, WhatsApp, and Google Calendar

## My Contribution

This repository contains my direct contributions to the backend system, including:

- Core API endpoints for `/invoke` and `/invoke_streamed`
- Agent orchestration and streaming logic
- MCP server configuration for Gmail, Slack, Notion, WhatsApp, Calendar, and more
- Integration of hierarchical agent logic using FastAPI and context-based decision routing

## Hackathon Outcome
We were awared second price and won a prize of INR 75,000


