# Development Style Guide

## Code Organization

### Directory Structure


## Python Coding Standards

### Import Organization


### Function Documentation


### Error Handling


## API Design Standards

### Response Format


### Endpoint Naming
- Use nouns for resources: , 
- Use HTTP methods appropriately: POST for creation, GET for retrieval
- Include resource identifiers: 

## Service Layer Patterns

### Dependency Injection


### Session Management


## Configuration Management

### Environment Variables


### Lazy Initialization


## Performance Guidelines

### Memory Efficiency
- Store only URLs in vector database, not full images
- Process HTML content in memory without disk I/O
- Use lazy loading for external resources

### Concurrency
- Implement thread-safe session management
- Use domain locking to prevent conflicts
- Limit concurrent operations with configurable maximums

## Documentation Standards

### Module Headers


### README Structure
- Clear project overview and features
- Installation and setup instructions
- API documentation with examples
- Architecture explanation
- Usage examples for different interfaces