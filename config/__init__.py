"""Configuration module for Relay."""

from config.config import Config, ModelConfig
from config.loader import load_config

__all__ = ['Config', 'ModelConfig', 'load_config']