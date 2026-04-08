"""
æ—¥å¿—é…ç½®æ¨¡å—
æä¾›ç»Ÿä¸€çš„æ—¥å¿—ç®¡ç†ï¼ŒåŒæ—¶è¾“å‡ºåˆ°æŽ§åˆ¶å°å’Œæ–‡ä»¶
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler


def _ensure_utf8_stdout():
    """
    ç¡®ä¿ stdout/stderr ä½¿ç”¨ UTF-8 ç¼–ç 
    è§£å†³ Windows æŽ§åˆ¶å°ä¸­æ–‡ä¹±ç é—®é¢˜
    """
    if sys.platform == 'win32':
        # Windows ä¸‹é‡æ–°é…ç½®æ ‡å‡†è¾“å‡ºä¸º UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# æ—¥å¿—ç›®å½•
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def setup_logger(name: str = 'posiedon', level: int = logging.DEBUG) -> logging.Logger:
    """
    è®¾ç½®æ—¥å¿—å™¨
    
    Args:
        name: æ—¥å¿—å™¨åç§°
        level: æ—¥å¿—çº§åˆ«
        
    Returns:
        é…ç½®å¥½çš„æ—¥å¿—å™¨
    """
    # ç¡®ä¿æ—¥å¿—ç›®å½•å­˜åœ¨
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # åˆ›å»ºæ—¥å¿—å™¨
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # é˜»æ­¢æ—¥å¿—å‘ä¸Šä¼ æ’­åˆ°æ ¹ loggerï¼Œé¿å…é‡å¤è¾“å‡º
    logger.propagate = False
    
    # å¦‚æžœå·²ç»æœ‰å¤„ç†å™¨ï¼Œä¸é‡å¤æ·»åŠ 
    if logger.handlers:
        return logger
    
    # æ—¥å¿—æ ¼å¼
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # 1. æ–‡ä»¶å¤„ç†å™¨ - è¯¦ç»†æ—¥å¿—ï¼ˆæŒ‰æ—¥æœŸå‘½åï¼Œå¸¦è½®è½¬ï¼‰
    log_filename = datetime.now().strftime('%Y-%m-%d') + '.log'
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_filename),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # 2. æŽ§åˆ¶å°å¤„ç†å™¨ - ç®€æ´æ—¥å¿—ï¼ˆINFOåŠä»¥ä¸Šï¼‰
    # ç¡®ä¿ Windows ä¸‹ä½¿ç”¨ UTF-8 ç¼–ç ï¼Œé¿å…ä¸­æ–‡ä¹±ç 
    _ensure_utf8_stdout()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # æ·»åŠ å¤„ç†å™¨
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str = 'posiedon') -> logging.Logger:
    """
    èŽ·å–æ—¥å¿—å™¨ï¼ˆå¦‚æžœä¸å­˜åœ¨åˆ™åˆ›å»ºï¼‰
    
    Args:
        name: æ—¥å¿—å™¨åç§°
        
    Returns:
        æ—¥å¿—å™¨å®žä¾‹
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# åˆ›å»ºé»˜è®¤æ—¥å¿—å™¨
logger = setup_logger()


# ä¾¿æ·æ–¹æ³•
def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    logger.critical(msg, *args, **kwargs)

