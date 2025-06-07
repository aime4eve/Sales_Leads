"""
DingTalk API Module

This module provides interfaces for interacting with DingTalk APIs.
"""

from .DingTalk import DingTalk
from .timeout_config import get_timeout, get_error_message, get_retry_strategy

__all__ = ['DingTalk', 'get_timeout', 'get_error_message', 'get_retry_strategy'] 