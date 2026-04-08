"""
Posiedon Backend å¯åŠ¨å…¥å£
"""

import os
import sys

# è§£å†³ Windows æŽ§åˆ¶å°ä¸­æ–‡ä¹±ç é—®é¢˜ï¼šåœ¨æ‰€æœ‰å¯¼å…¥ä¹‹å‰è®¾ç½® UTF-8 ç¼–ç 
if sys.platform == 'win32':
    # è®¾ç½®çŽ¯å¢ƒå˜é‡ç¡®ä¿ Python ä½¿ç”¨ UTF-8
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    # é‡æ–°é…ç½®æ ‡å‡†è¾“å‡ºæµä¸º UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# æ·»åŠ é¡¹ç›®æ ¹ç›®å½•åˆ°è·¯å¾„
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config


def main():
    """ä¸»å‡½æ•°"""
    # éªŒè¯é…ç½®
    errors = Config.validate()
    if errors:
        print("é…ç½®é”™è¯¯:")
        for err in errors:
            print(f"  - {err}")
        print("\nè¯·æ£€æŸ¥ .env æ–‡ä»¶ä¸­çš„é…ç½®")
        sys.exit(1)
    
    # åˆ›å»ºåº”ç”¨
    app = create_app()
    
    # èŽ·å–è¿è¡Œé…ç½®
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = Config.DEBUG
    
    # å¯åŠ¨æœåŠ¡
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()

