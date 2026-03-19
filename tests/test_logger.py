"""Logger modülü testleri."""
import logging
from src.core.logger import setup_logger

def test_logger_creation():
    logger = setup_logger("test_logger_123")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger_123"
    assert len(logger.handlers) >= 1
    
    # İkinci defa aynı ismi çağırırsak mevcut handler ile gelmeli
    logger2 = setup_logger("test_logger_123")
    assert logger is logger2
