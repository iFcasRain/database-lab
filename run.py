"""启动入口：python run.py

默认监听 http://127.0.0.1:5000，可通过环境变量 HOST / PORT 覆盖。
"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    print("小卖部经营管理 v1.0 已启动：http://%s:%d" % (host, port))
    app.run(host=host, port=port, debug=debug)
