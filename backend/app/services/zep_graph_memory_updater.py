"""
Zepå›¾è°±è®°å¿†æ›´æ–°æœåŠ¡
å°†æ¨¡æ‹Ÿä¸­çš„Agentæ´»åŠ¨åŠ¨æ€æ›´æ–°åˆ°Zepå›¾è°±ä¸­
"""

import os
import time
import threading
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import get_locale, set_locale

logger = get_logger('posiedon.zep_graph_memory_updater')


@dataclass
class AgentActivity:
    """Agentæ´»åŠ¨è®°å½•"""
    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str
    
    def to_episode_text(self) -> str:
        """
        å°†æ´»åŠ¨è½¬æ¢ä¸ºå¯ä»¥å‘é€ç»™Zepçš„æ–‡æœ¬æè¿°
        
        é‡‡ç”¨è‡ªç„¶è¯­è¨€æè¿°æ ¼å¼ï¼Œè®©Zepèƒ½å¤Ÿä»Žä¸­æå–å®žä½“å’Œå…³ç³»
        ä¸æ·»åŠ æ¨¡æ‹Ÿç›¸å…³çš„å‰ç¼€ï¼Œé¿å…è¯¯å¯¼å›¾è°±æ›´æ–°
        """
        # æ ¹æ®ä¸åŒçš„åŠ¨ä½œç±»åž‹ç”Ÿæˆä¸åŒçš„æè¿°
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }
        
        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()
        
        # ç›´æŽ¥è¿”å›ž "agentåç§°: æ´»åŠ¨æè¿°" æ ¼å¼ï¼Œä¸æ·»åŠ æ¨¡æ‹Ÿå‰ç¼€
        return f"{self.agent_name}: {description}"
    
    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"å‘å¸ƒäº†ä¸€æ¡å¸–å­ï¼šã€Œ{content}ã€"
        return "å‘å¸ƒäº†ä¸€æ¡å¸–å­"
    
    def _describe_like_post(self) -> str:
        """ç‚¹èµžå¸–å­ - åŒ…å«å¸–å­åŽŸæ–‡å’Œä½œè€…ä¿¡æ¯"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if post_content and post_author:
            return f"ç‚¹èµžäº†{post_author}çš„å¸–å­ï¼šã€Œ{post_content}ã€"
        elif post_content:
            return f"ç‚¹èµžäº†ä¸€æ¡å¸–å­ï¼šã€Œ{post_content}ã€"
        elif post_author:
            return f"ç‚¹èµžäº†{post_author}çš„ä¸€æ¡å¸–å­"
        return "ç‚¹èµžäº†ä¸€æ¡å¸–å­"
    
    def _describe_dislike_post(self) -> str:
        """è¸©å¸–å­ - åŒ…å«å¸–å­åŽŸæ–‡å’Œä½œè€…ä¿¡æ¯"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if post_content and post_author:
            return f"è¸©äº†{post_author}çš„å¸–å­ï¼šã€Œ{post_content}ã€"
        elif post_content:
            return f"è¸©äº†ä¸€æ¡å¸–å­ï¼šã€Œ{post_content}ã€"
        elif post_author:
            return f"è¸©äº†{post_author}çš„ä¸€æ¡å¸–å­"
        return "è¸©äº†ä¸€æ¡å¸–å­"
    
    def _describe_repost(self) -> str:
        """è½¬å‘å¸–å­ - åŒ…å«åŽŸå¸–å†…å®¹å’Œä½œè€…ä¿¡æ¯"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        
        if original_content and original_author:
            return f"è½¬å‘äº†{original_author}çš„å¸–å­ï¼šã€Œ{original_content}ã€"
        elif original_content:
            return f"è½¬å‘äº†ä¸€æ¡å¸–å­ï¼šã€Œ{original_content}ã€"
        elif original_author:
            return f"è½¬å‘äº†{original_author}çš„ä¸€æ¡å¸–å­"
        return "è½¬å‘äº†ä¸€æ¡å¸–å­"
    
    def _describe_quote_post(self) -> str:
        """å¼•ç”¨å¸–å­ - åŒ…å«åŽŸå¸–å†…å®¹ã€ä½œè€…ä¿¡æ¯å’Œå¼•ç”¨è¯„è®º"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")
        
        base = ""
        if original_content and original_author:
            base = f"å¼•ç”¨äº†{original_author}çš„å¸–å­ã€Œ{original_content}ã€"
        elif original_content:
            base = f"å¼•ç”¨äº†ä¸€æ¡å¸–å­ã€Œ{original_content}ã€"
        elif original_author:
            base = f"å¼•ç”¨äº†{original_author}çš„ä¸€æ¡å¸–å­"
        else:
            base = "å¼•ç”¨äº†ä¸€æ¡å¸–å­"
        
        if quote_content:
            base += f"ï¼Œå¹¶è¯„è®ºé“ï¼šã€Œ{quote_content}ã€"
        return base
    
    def _describe_follow(self) -> str:
        """å…³æ³¨ç”¨æˆ· - åŒ…å«è¢«å…³æ³¨ç”¨æˆ·çš„åç§°"""
        target_user_name = self.action_args.get("target_user_name", "")
        
        if target_user_name:
            return f"å…³æ³¨äº†ç”¨æˆ·ã€Œ{target_user_name}ã€"
        return "å…³æ³¨äº†ä¸€ä¸ªç”¨æˆ·"
    
    def _describe_create_comment(self) -> str:
        """å‘è¡¨è¯„è®º - åŒ…å«è¯„è®ºå†…å®¹å’Œæ‰€è¯„è®ºçš„å¸–å­ä¿¡æ¯"""
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")
        
        if content:
            if post_content and post_author:
                return f"åœ¨{post_author}çš„å¸–å­ã€Œ{post_content}ã€ä¸‹è¯„è®ºé“ï¼šã€Œ{content}ã€"
            elif post_content:
                return f"åœ¨å¸–å­ã€Œ{post_content}ã€ä¸‹è¯„è®ºé“ï¼šã€Œ{content}ã€"
            elif post_author:
                return f"åœ¨{post_author}çš„å¸–å­ä¸‹è¯„è®ºé“ï¼šã€Œ{content}ã€"
            return f"è¯„è®ºé“ï¼šã€Œ{content}ã€"
        return "å‘è¡¨äº†è¯„è®º"
    
    def _describe_like_comment(self) -> str:
        """ç‚¹èµžè¯„è®º - åŒ…å«è¯„è®ºå†…å®¹å’Œä½œè€…ä¿¡æ¯"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        
        if comment_content and comment_author:
            return f"ç‚¹èµžäº†{comment_author}çš„è¯„è®ºï¼šã€Œ{comment_content}ã€"
        elif comment_content:
            return f"ç‚¹èµžäº†ä¸€æ¡è¯„è®ºï¼šã€Œ{comment_content}ã€"
        elif comment_author:
            return f"ç‚¹èµžäº†{comment_author}çš„ä¸€æ¡è¯„è®º"
        return "ç‚¹èµžäº†ä¸€æ¡è¯„è®º"
    
    def _describe_dislike_comment(self) -> str:
        """è¸©è¯„è®º - åŒ…å«è¯„è®ºå†…å®¹å’Œä½œè€…ä¿¡æ¯"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")
        
        if comment_content and comment_author:
            return f"è¸©äº†{comment_author}çš„è¯„è®ºï¼šã€Œ{comment_content}ã€"
        elif comment_content:
            return f"è¸©äº†ä¸€æ¡è¯„è®ºï¼šã€Œ{comment_content}ã€"
        elif comment_author:
            return f"è¸©äº†{comment_author}çš„ä¸€æ¡è¯„è®º"
        return "è¸©äº†ä¸€æ¡è¯„è®º"
    
    def _describe_search(self) -> str:
        """æœç´¢å¸–å­ - åŒ…å«æœç´¢å…³é”®è¯"""
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"æœç´¢äº†ã€Œ{query}ã€" if query else "è¿›è¡Œäº†æœç´¢"
    
    def _describe_search_user(self) -> str:
        """æœç´¢ç”¨æˆ· - åŒ…å«æœç´¢å…³é”®è¯"""
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"æœç´¢äº†ç”¨æˆ·ã€Œ{query}ã€" if query else "æœç´¢äº†ç”¨æˆ·"
    
    def _describe_mute(self) -> str:
        """å±è”½ç”¨æˆ· - åŒ…å«è¢«å±è”½ç”¨æˆ·çš„åç§°"""
        target_user_name = self.action_args.get("target_user_name", "")
        
        if target_user_name:
            return f"å±è”½äº†ç”¨æˆ·ã€Œ{target_user_name}ã€"
        return "å±è”½äº†ä¸€ä¸ªç”¨æˆ·"
    
    def _describe_generic(self) -> str:
        # å¯¹äºŽæœªçŸ¥çš„åŠ¨ä½œç±»åž‹ï¼Œç”Ÿæˆé€šç”¨æè¿°
        return f"æ‰§è¡Œäº†{self.action_type}æ“ä½œ"


class ZepGraphMemoryUpdater:
    """
    Zepå›¾è°±è®°å¿†æ›´æ–°å™¨
    
    ç›‘æŽ§æ¨¡æ‹Ÿçš„actionsæ—¥å¿—æ–‡ä»¶ï¼Œå°†æ–°çš„agentæ´»åŠ¨å®žæ—¶æ›´æ–°åˆ°Zepå›¾è°±ä¸­ã€‚
    æŒ‰å¹³å°åˆ†ç»„ï¼Œæ¯ç´¯ç§¯BATCH_SIZEæ¡æ´»åŠ¨åŽæ‰¹é‡å‘é€åˆ°Zepã€‚
    
    æ‰€æœ‰æœ‰æ„ä¹‰çš„è¡Œä¸ºéƒ½ä¼šè¢«æ›´æ–°åˆ°Zepï¼Œaction_argsä¸­ä¼šåŒ…å«å®Œæ•´çš„ä¸Šä¸‹æ–‡ä¿¡æ¯ï¼š
    - ç‚¹èµž/è¸©çš„å¸–å­åŽŸæ–‡
    - è½¬å‘/å¼•ç”¨çš„å¸–å­åŽŸæ–‡
    - å…³æ³¨/å±è”½çš„ç”¨æˆ·å
    - ç‚¹èµž/è¸©çš„è¯„è®ºåŽŸæ–‡
    """
    
    # æ‰¹é‡å‘é€å¤§å°ï¼ˆæ¯ä¸ªå¹³å°ç´¯ç§¯å¤šå°‘æ¡åŽå‘é€ï¼‰
    BATCH_SIZE = 5
    
    # å¹³å°åç§°æ˜ å°„ï¼ˆç”¨äºŽæŽ§åˆ¶å°æ˜¾ç¤ºï¼‰
    PLATFORM_DISPLAY_NAMES = {
        'twitter': 'ä¸–ç•Œ1',
        'reddit': 'ä¸–ç•Œ2',
    }
    
    # å‘é€é—´éš”ï¼ˆç§’ï¼‰ï¼Œé¿å…è¯·æ±‚è¿‡å¿«
    SEND_INTERVAL = 0.5
    
    # é‡è¯•é…ç½®
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # ç§’
    
    def __init__(self, graph_id: str, api_key: Optional[str] = None):
        """
        åˆå§‹åŒ–æ›´æ–°å™¨
        
        Args:
            graph_id: Zepå›¾è°±ID
            api_key: Zep API Keyï¼ˆå¯é€‰ï¼Œé»˜è®¤ä»Žé…ç½®è¯»å–ï¼‰
        """
        self.graph_id = graph_id
        self.api_key = api_key or Config.ZEP_API_KEY
        
        if not self.api_key:
            raise ValueError("ZEP_API_KEYæœªé…ç½®")
        
        self.client = Zep(api_key=self.api_key)
        
        # æ´»åŠ¨é˜Ÿåˆ—
        self._activity_queue: Queue = Queue()
        
        # æŒ‰å¹³å°åˆ†ç»„çš„æ´»åŠ¨ç¼“å†²åŒºï¼ˆæ¯ä¸ªå¹³å°å„è‡ªç´¯ç§¯åˆ°BATCH_SIZEåŽæ‰¹é‡å‘é€ï¼‰
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()
        
        # æŽ§åˆ¶æ ‡å¿—
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # ç»Ÿè®¡
        self._total_activities = 0  # å®žé™…æ·»åŠ åˆ°é˜Ÿåˆ—çš„æ´»åŠ¨æ•°
        self._total_sent = 0        # æˆåŠŸå‘é€åˆ°Zepçš„æ‰¹æ¬¡æ•°
        self._total_items_sent = 0  # æˆåŠŸå‘é€åˆ°Zepçš„æ´»åŠ¨æ¡æ•°
        self._failed_count = 0      # å‘é€å¤±è´¥çš„æ‰¹æ¬¡æ•°
        self._skipped_count = 0     # è¢«è¿‡æ»¤è·³è¿‡çš„æ´»åŠ¨æ•°ï¼ˆDO_NOTHINGï¼‰
        
        logger.info(f"ZepGraphMemoryUpdater åˆå§‹åŒ–å®Œæˆ: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")
    
    def _get_platform_display_name(self, platform: str) -> str:
        """èŽ·å–å¹³å°çš„æ˜¾ç¤ºåç§°"""
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)
    
    def start(self):
        """å¯åŠ¨åŽå°å·¥ä½œçº¿ç¨‹"""
        if self._running:
            return

        # Capture locale before spawning background thread
        current_locale = get_locale()

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            args=(current_locale,),
            daemon=True,
            name=f"ZepMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"ZepGraphMemoryUpdater å·²å¯åŠ¨: graph_id={self.graph_id}")
    
    def stop(self):
        """åœæ­¢åŽå°å·¥ä½œçº¿ç¨‹"""
        self._running = False
        
        # å‘é€å‰©ä½™çš„æ´»åŠ¨
        self._flush_remaining()
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        
        logger.info(f"ZepGraphMemoryUpdater å·²åœæ­¢: graph_id={self.graph_id}, "
                   f"total_activities={self._total_activities}, "
                   f"batches_sent={self._total_sent}, "
                   f"items_sent={self._total_items_sent}, "
                   f"failed={self._failed_count}, "
                   f"skipped={self._skipped_count}")
    
    def add_activity(self, activity: AgentActivity):
        """
        æ·»åŠ ä¸€ä¸ªagentæ´»åŠ¨åˆ°é˜Ÿåˆ—
        
        æ‰€æœ‰æœ‰æ„ä¹‰çš„è¡Œä¸ºéƒ½ä¼šè¢«æ·»åŠ åˆ°é˜Ÿåˆ—ï¼ŒåŒ…æ‹¬ï¼š
        - CREATE_POSTï¼ˆå‘å¸–ï¼‰
        - CREATE_COMMENTï¼ˆè¯„è®ºï¼‰
        - QUOTE_POSTï¼ˆå¼•ç”¨å¸–å­ï¼‰
        - SEARCH_POSTSï¼ˆæœç´¢å¸–å­ï¼‰
        - SEARCH_USERï¼ˆæœç´¢ç”¨æˆ·ï¼‰
        - LIKE_POST/DISLIKE_POSTï¼ˆç‚¹èµž/è¸©å¸–å­ï¼‰
        - REPOSTï¼ˆè½¬å‘ï¼‰
        - FOLLOWï¼ˆå…³æ³¨ï¼‰
        - MUTEï¼ˆå±è”½ï¼‰
        - LIKE_COMMENT/DISLIKE_COMMENTï¼ˆç‚¹èµž/è¸©è¯„è®ºï¼‰
        
        action_argsä¸­ä¼šåŒ…å«å®Œæ•´çš„ä¸Šä¸‹æ–‡ä¿¡æ¯ï¼ˆå¦‚å¸–å­åŽŸæ–‡ã€ç”¨æˆ·åç­‰ï¼‰ã€‚
        
        Args:
            activity: Agentæ´»åŠ¨è®°å½•
        """
        # è·³è¿‡DO_NOTHINGç±»åž‹çš„æ´»åŠ¨
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return
        
        self._activity_queue.put(activity)
        self._total_activities += 1
        logger.debug(f"æ·»åŠ æ´»åŠ¨åˆ°Zepé˜Ÿåˆ—: {activity.agent_name} - {activity.action_type}")
    
    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        """
        ä»Žå­—å…¸æ•°æ®æ·»åŠ æ´»åŠ¨
        
        Args:
            data: ä»Žactions.jsonlè§£æžçš„å­—å…¸æ•°æ®
            platform: å¹³å°åç§° (twitter/reddit)
        """
        # è·³è¿‡äº‹ä»¶ç±»åž‹çš„æ¡ç›®
        if "event_type" in data:
            return
        
        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )
        
        self.add_activity(activity)
    
    def _worker_loop(self, locale: str = 'zh'):
        """åŽå°å·¥ä½œå¾ªçŽ¯ - æŒ‰å¹³å°æ‰¹é‡å‘é€æ´»åŠ¨åˆ°Zep"""
        set_locale(locale)
        while self._running or not self._activity_queue.empty():
            try:
                # å°è¯•ä»Žé˜Ÿåˆ—èŽ·å–æ´»åŠ¨ï¼ˆè¶…æ—¶1ç§’ï¼‰
                try:
                    activity = self._activity_queue.get(timeout=1)
                    
                    # å°†æ´»åŠ¨æ·»åŠ åˆ°å¯¹åº”å¹³å°çš„ç¼“å†²åŒº
                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)
                        
                        # æ£€æŸ¥è¯¥å¹³å°æ˜¯å¦è¾¾åˆ°æ‰¹é‡å¤§å°
                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][:self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE:]
                            # é‡Šæ”¾é”åŽå†å‘é€
                            self._send_batch_activities(batch, platform)
                            # å‘é€é—´éš”ï¼Œé¿å…è¯·æ±‚è¿‡å¿«
                            time.sleep(self.SEND_INTERVAL)
                    
                except Empty:
                    pass
                    
            except Exception as e:
                logger.error(f"å·¥ä½œå¾ªçŽ¯å¼‚å¸¸: {e}")
                time.sleep(1)
    
    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        """
        æ‰¹é‡å‘é€æ´»åŠ¨åˆ°Zepå›¾è°±ï¼ˆåˆå¹¶ä¸ºä¸€æ¡æ–‡æœ¬ï¼‰
        
        Args:
            activities: Agentæ´»åŠ¨åˆ—è¡¨
            platform: å¹³å°åç§°
        """
        if not activities:
            return
        
        # å°†å¤šæ¡æ´»åŠ¨åˆå¹¶ä¸ºä¸€æ¡æ–‡æœ¬ï¼Œç”¨æ¢è¡Œåˆ†éš”
        episode_texts = [activity.to_episode_text() for activity in activities]
        combined_text = "\n".join(episode_texts)
        
        # å¸¦é‡è¯•çš„å‘é€
        for attempt in range(self.MAX_RETRIES):
            try:
                self.client.graph.add(
                    graph_id=self.graph_id,
                    type="text",
                    data=combined_text
                )
                
                self._total_sent += 1
                self._total_items_sent += len(activities)
                display_name = self._get_platform_display_name(platform)
                logger.info(f"æˆåŠŸæ‰¹é‡å‘é€ {len(activities)} æ¡{display_name}æ´»åŠ¨åˆ°å›¾è°± {self.graph_id}")
                logger.debug(f"æ‰¹é‡å†…å®¹é¢„è§ˆ: {combined_text[:200]}...")
                return
                
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"æ‰¹é‡å‘é€åˆ°Zepå¤±è´¥ (å°è¯• {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"æ‰¹é‡å‘é€åˆ°Zepå¤±è´¥ï¼Œå·²é‡è¯•{self.MAX_RETRIES}æ¬¡: {e}")
                    self._failed_count += 1
    
    def _flush_remaining(self):
        """å‘é€é˜Ÿåˆ—å’Œç¼“å†²åŒºä¸­å‰©ä½™çš„æ´»åŠ¨"""
        # é¦–å…ˆå¤„ç†é˜Ÿåˆ—ä¸­å‰©ä½™çš„æ´»åŠ¨ï¼Œæ·»åŠ åˆ°ç¼“å†²åŒº
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break
        
        # ç„¶åŽå‘é€å„å¹³å°ç¼“å†²åŒºä¸­å‰©ä½™çš„æ´»åŠ¨ï¼ˆå³ä½¿ä¸è¶³BATCH_SIZEæ¡ï¼‰
        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display_name = self._get_platform_display_name(platform)
                    logger.info(f"å‘é€{display_name}å¹³å°å‰©ä½™çš„ {len(buffer)} æ¡æ´»åŠ¨")
                    self._send_batch_activities(buffer, platform)
            # æ¸…ç©ºæ‰€æœ‰ç¼“å†²åŒº
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []
    
    def get_stats(self) -> Dict[str, Any]:
        """èŽ·å–ç»Ÿè®¡ä¿¡æ¯"""
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}
        
        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,  # æ·»åŠ åˆ°é˜Ÿåˆ—çš„æ´»åŠ¨æ€»æ•°
            "batches_sent": self._total_sent,            # æˆåŠŸå‘é€çš„æ‰¹æ¬¡æ•°
            "items_sent": self._total_items_sent,        # æˆåŠŸå‘é€çš„æ´»åŠ¨æ¡æ•°
            "failed_count": self._failed_count,          # å‘é€å¤±è´¥çš„æ‰¹æ¬¡æ•°
            "skipped_count": self._skipped_count,        # è¢«è¿‡æ»¤è·³è¿‡çš„æ´»åŠ¨æ•°ï¼ˆDO_NOTHINGï¼‰
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,                # å„å¹³å°ç¼“å†²åŒºå¤§å°
            "running": self._running,
        }


class ZepGraphMemoryManager:
    """
    ç®¡ç†å¤šä¸ªæ¨¡æ‹Ÿçš„Zepå›¾è°±è®°å¿†æ›´æ–°å™¨
    
    æ¯ä¸ªæ¨¡æ‹Ÿå¯ä»¥æœ‰è‡ªå·±çš„æ›´æ–°å™¨å®žä¾‹
    """
    
    _updaters: Dict[str, ZepGraphMemoryUpdater] = {}
    _lock = threading.Lock()
    
    @classmethod
    def create_updater(cls, simulation_id: str, graph_id: str) -> ZepGraphMemoryUpdater:
        """
        ä¸ºæ¨¡æ‹Ÿåˆ›å»ºå›¾è°±è®°å¿†æ›´æ–°å™¨
        
        Args:
            simulation_id: æ¨¡æ‹ŸID
            graph_id: Zepå›¾è°±ID
            
        Returns:
            ZepGraphMemoryUpdaterå®žä¾‹
        """
        with cls._lock:
            # å¦‚æžœå·²å­˜åœ¨ï¼Œå…ˆåœæ­¢æ—§çš„
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
            
            updater = ZepGraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater
            
            logger.info(f"åˆ›å»ºå›¾è°±è®°å¿†æ›´æ–°å™¨: simulation_id={simulation_id}, graph_id={graph_id}")
            return updater
    
    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[ZepGraphMemoryUpdater]:
        """èŽ·å–æ¨¡æ‹Ÿçš„æ›´æ–°å™¨"""
        return cls._updaters.get(simulation_id)
    
    @classmethod
    def stop_updater(cls, simulation_id: str):
        """åœæ­¢å¹¶ç§»é™¤æ¨¡æ‹Ÿçš„æ›´æ–°å™¨"""
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]
                logger.info(f"å·²åœæ­¢å›¾è°±è®°å¿†æ›´æ–°å™¨: simulation_id={simulation_id}")
    
    # é˜²æ­¢ stop_all é‡å¤è°ƒç”¨çš„æ ‡å¿—
    _stop_all_done = False
    
    @classmethod
    def stop_all(cls):
        """åœæ­¢æ‰€æœ‰æ›´æ–°å™¨"""
        # é˜²æ­¢é‡å¤è°ƒç”¨
        if cls._stop_all_done:
            return
        cls._stop_all_done = True
        
        with cls._lock:
            if cls._updaters:
                for simulation_id, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(f"åœæ­¢æ›´æ–°å™¨å¤±è´¥: simulation_id={simulation_id}, error={e}")
                cls._updaters.clear()
            logger.info("å·²åœæ­¢æ‰€æœ‰å›¾è°±è®°å¿†æ›´æ–°å™¨")
    
    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """èŽ·å–æ‰€æœ‰æ›´æ–°å™¨çš„ç»Ÿè®¡ä¿¡æ¯"""
        return {
            sim_id: updater.get_stats() 
            for sim_id, updater in cls._updaters.items()
        }
