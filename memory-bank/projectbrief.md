# Image Chat - Project Brief

## Project Overview
**Image Chat** is an intelligent website crawler and AI-powered image search system designed for production use. The system intelligently crawls websites, extracts images, and provides powerful natural language search capabilities using semantic understanding.

## Primary Purpose
Build a production-ready, modular system that combines web crawling, image extraction, and AI-powered search to enable natural language querying of images across websites.

## Target Users
- Content managers and SEO professionals
- Researchers conducting competitive analysis
- Developers building dynamic website content systems
- Anyone needing intelligent image discovery and cataloging

## Core Value Proposition
- **Memory-efficient architecture**: URL-only vector storage with lazy image loading
- **Production-ready modularity**: Service layer pattern with clean separation of concerns
- **Smart crawling strategy**: JavaScript rendering with context-aware extraction
- **Real-time monitoring**: SSE with polling fallback for live progress updates

## Success Criteria
1. Successfully crawl JavaScript-heavy websites with full image extraction
2. Provide accurate natural language search with semantic understanding
3. Handle concurrent operations with proper resource isolation
4. Maintain production-ready performance and scalability
5. Support multiple interfaces (CLI, Web UI, REST API)

## Technical Foundation
- **Backend**: Python Flask with Blueprint architecture
- **AI/ML**: OpenAI embeddings, LangChain for orchestration
- **Vector Database**: Pinecone for semantic search storage
- **Web Crawling**: Firecrawl for JavaScript rendering
- **Real-time**: Server-Sent Events with polling fallback
- **Processing**: BeautifulSoup4 for HTML parsing

## Project Constraints
- Must support concurrent crawling with domain locking
- Memory-efficient processing without disk I/O
- Production-ready error handling and resource management
- API key dependencies (OpenAI, Firecrawl, Pinecone)
- Cross-platform compatibility (Web, CLI, API)