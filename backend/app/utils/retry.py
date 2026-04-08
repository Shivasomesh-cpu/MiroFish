"""
APIè°ƒç”¨é‡è¯•æœºåˆ¶
ç”¨äºŽå¤„ç†LLMç­‰å¤–éƒ¨APIè°ƒç”¨çš„é‡è¯•é€»è¾‘
"""

import time
import random
import functools
from typing import Callable, Any, Optional, Type, Tuple
from ..utils.logger import get_logger

logger = get_logger('posiedon.retry')


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    å¸¦æŒ‡æ•°é€€é¿çš„é‡è¯•è£…é¥°å™¨
    
    Args:
        max_retries: æœ€å¤§é‡è¯•æ¬¡æ•°
        initial_delay: åˆå§‹å»¶è¿Ÿï¼ˆç§’ï¼‰
        max_delay: æœ€å¤§å»¶è¿Ÿï¼ˆç§’ï¼‰
        backoff_factor: é€€é¿å› å­
        jitter: æ˜¯å¦æ·»åŠ éšæœºæŠ–åŠ¨
        exceptions: éœ€è¦é‡è¯•çš„å¼‚å¸¸ç±»åž‹
        on_retry: é‡è¯•æ—¶çš„å›žè°ƒå‡½æ•° (exception, retry_count)
    
    Usage:
        @retry_with_backoff(max_retries=3)
        def call_llm_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"å‡½æ•° {func.__name__} åœ¨ {max_retries} æ¬¡é‡è¯•åŽä»å¤±è´¥: {str(e)}")
                        raise
                    
                    # è®¡ç®—å»¶è¿Ÿ
                    current_delay = min(delay, max_delay)
                    if jitter:
                        current_delay = current_delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"å‡½æ•° {func.__name__} ç¬¬ {attempt + 1} æ¬¡å°è¯•å¤±è´¥: {str(e)}, "
                        f"{current_delay:.1f}ç§’åŽé‡è¯•..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt + 1)
                    
                    time.sleep(current_delay)
                    delay *= backoff_factor
            
            raise last_exception
        
        return wrapper
    return decorator


def retry_with_backoff_async(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    å¼‚æ­¥ç‰ˆæœ¬çš„é‡è¯•è£…é¥°å™¨
    """
    import asyncio
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"å¼‚æ­¥å‡½æ•° {func.__name__} åœ¨ {max_retries} æ¬¡é‡è¯•åŽä»å¤±è´¥: {str(e)}")
                        raise
                    
                    current_delay = min(delay, max_delay)
                    if jitter:
                        current_delay = current_delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"å¼‚æ­¥å‡½æ•° {func.__name__} ç¬¬ {attempt + 1} æ¬¡å°è¯•å¤±è´¥: {str(e)}, "
                        f"{current_delay:.1f}ç§’åŽé‡è¯•..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt + 1)
                    
                    await asyncio.sleep(current_delay)
                    delay *= backoff_factor
            
            raise last_exception
        
        return wrapper
    return decorator


class RetryableAPIClient:
    """
    å¯é‡è¯•çš„APIå®¢æˆ·ç«¯å°è£…
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
    
    def call_with_retry(
        self,
        func: Callable,
        *args,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        **kwargs
    ) -> Any:
        """
        æ‰§è¡Œå‡½æ•°è°ƒç”¨å¹¶åœ¨å¤±è´¥æ—¶é‡è¯•
        
        Args:
            func: è¦è°ƒç”¨çš„å‡½æ•°
            *args: å‡½æ•°å‚æ•°
            exceptions: éœ€è¦é‡è¯•çš„å¼‚å¸¸ç±»åž‹
            **kwargs: å‡½æ•°å…³é”®å­—å‚æ•°
            
        Returns:
            å‡½æ•°è¿”å›žå€¼
        """
        last_exception = None
        delay = self.initial_delay
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
                
            except exceptions as e:
                last_exception = e
                
                if attempt == self.max_retries:
                    logger.error(f"APIè°ƒç”¨åœ¨ {self.max_retries} æ¬¡é‡è¯•åŽä»å¤±è´¥: {str(e)}")
                    raise
                
                current_delay = min(delay, self.max_delay)
                current_delay = current_delay * (0.5 + random.random())
                
                logger.warning(
                    f"APIè°ƒç”¨ç¬¬ {attempt + 1} æ¬¡å°è¯•å¤±è´¥: {str(e)}, "
                    f"{current_delay:.1f}ç§’åŽé‡è¯•..."
                )
                
                time.sleep(current_delay)
                delay *= self.backoff_factor
        
        raise last_exception
    
    def call_batch_with_retry(
        self,
        items: list,
        process_func: Callable,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        continue_on_failure: bool = True
    ) -> Tuple[list, list]:
        """
        æ‰¹é‡è°ƒç”¨å¹¶å¯¹æ¯ä¸ªå¤±è´¥é¡¹å•ç‹¬é‡è¯•
        
        Args:
            items: è¦å¤„ç†çš„é¡¹ç›®åˆ—è¡¨
            process_func: å¤„ç†å‡½æ•°ï¼ŒæŽ¥æ”¶å•ä¸ªitemä½œä¸ºå‚æ•°
            exceptions: éœ€è¦é‡è¯•çš„å¼‚å¸¸ç±»åž‹
            continue_on_failure: å•é¡¹å¤±è´¥åŽæ˜¯å¦ç»§ç»­å¤„ç†å…¶ä»–é¡¹
            
        Returns:
            (æˆåŠŸç»“æžœåˆ—è¡¨, å¤±è´¥é¡¹åˆ—è¡¨)
        """
        results = []
        failures = []
        
        for idx, item in enumerate(items):
            try:
                result = self.call_with_retry(
                    process_func,
                    item,
                    exceptions=exceptions
                )
                results.append(result)
                
            except Exception as e:
                logger.error(f"å¤„ç†ç¬¬ {idx + 1} é¡¹å¤±è´¥: {str(e)}")
                failures.append({
                    "index": idx,
                    "item": item,
                    "error": str(e)
                })
                
                if not continue_on_failure:
                    raise
        
        return results, failures

