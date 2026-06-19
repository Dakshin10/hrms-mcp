class AppError(Exception):
    """Base application exception."""
    pass

class D1Error(AppError):
    """Exception raised for database operations errors."""
    pass

class SQLValidationError(AppError):
    """Exception raised for SQL query safety/validation violations."""
    pass

class LLMError(AppError):
    """Exception raised for LLM generation/invocation failures."""
    pass

class MCPToolError(AppError):
    """Exception raised when an MCP tool fails and needs to return a clean message to the client."""
    pass

