import pytest
import os

# Set test environment variables before any imports
os.environ["ANTHROPIC_API_KEY"] = "test-key-for-testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_jobhunter.db"
