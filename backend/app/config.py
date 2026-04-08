"""
é…ç½®ç®¡ç†
ç»Ÿä¸€ä»Žé¡¹ç›®æ ¹ç›®å½•çš„ .env æ–‡ä»¶åŠ è½½é…ç½®
"""

import os
from dotenv import load_dotenv

# åŠ è½½é¡¹ç›®æ ¹ç›®å½•çš„ .env æ–‡ä»¶
# è·¯å¾„: Posiedon/.env (ç›¸å¯¹äºŽ backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # å¦‚æžœæ ¹ç›®å½•æ²¡æœ‰ .envï¼Œå°è¯•åŠ è½½çŽ¯å¢ƒå˜é‡ï¼ˆç”¨äºŽç”Ÿäº§çŽ¯å¢ƒï¼‰
    load_dotenv(override=True)


class Config:
    """Flaské…ç½®ç±»"""
    
    # Flaské…ç½®
    SECRET_KEY = os.environ.get('SECRET_KEY', 'posiedon-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSONé…ç½® - ç¦ç”¨ASCIIè½¬ä¹‰ï¼Œè®©ä¸­æ–‡ç›´æŽ¥æ˜¾ç¤ºï¼ˆè€Œä¸æ˜¯ \uXXXX æ ¼å¼ï¼‰
    JSON_AS_ASCII = False
    
    # LLMé…ç½®ï¼ˆç»Ÿä¸€ä½¿ç”¨OpenAIæ ¼å¼ï¼‰
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # Zepé…ç½®
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # æ–‡ä»¶ä¸Šä¼ é…ç½®
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # æ–‡æœ¬å¤„ç†é…ç½®
    DEFAULT_CHUNK_SIZE = 500  # é»˜è®¤åˆ‡å—å¤§å°
    DEFAULT_CHUNK_OVERLAP = 50  # é»˜è®¤é‡å å¤§å°
    
    # OASISæ¨¡æ‹Ÿé…ç½®
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASISå¹³å°å¯ç”¨åŠ¨ä½œé…ç½®
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agenté…ç½®
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls):
        """éªŒè¯å¿…è¦é…ç½®"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY æœªé…ç½®")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY æœªé…ç½®")
        return errors

