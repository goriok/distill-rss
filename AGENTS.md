# AI Agents in Distill RSS 🤖

## Role

In **Distill RSS**, the AI Agent acts as a **Curator** and **Critic**. It assumes the persona of a Senior Software Engineer specializing in Go (Golang) and Python.

## Responsibilities

1.  **Relevance Scoring (0-10)**:
    - Evaluates how useful an article is for a Go/Python expert.
    - Filters out beginner tutorials ("Hello World") or unrelated tech news unless they have significant architectural impact.

2.  **Summarization**:
    - Provides a one-sentence reason for its relevance.
    - Extracts key takeaways from the provided summary.

3.  **Tagging**:
    - Suggests up to 3 relevant tags (e.g., `performance`, `concurrency`, `system-design`).

## Prompt Strategy

The agent receives a structured prompt containing:
- **Persona**: Senior Software Engineer (Go/Python).
- **Context**: Keywords of interest (from `config.json`).
- **Input**: Article Title, Source, and Truncated Summary (max 500 chars).

### Optimization Techniques

To ensure efficiency and low cost:
- **Hard Filtering (Pre-AI)**: Articles are only sent to the agent if they contain at least one keyword in the title/summary.
- **Input Truncation**: Summaries are limited to 500 characters to reduce token usage.
- **Structured Output**: The agent is instructed to return pure JSON for easy parsing.

## Model Configuration

- **Default Model**: `gemini-1.5-flash` (balanced for speed/cost).
- **Environment Variable**: `GEMINI_MODEL` can be used to switch to newer models (e.g., `gemini-2.0-flash`) as they become available.
