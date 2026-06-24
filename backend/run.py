import os
from dotenv import load_dotenv

# .env はプロジェクトルート（backend/ の一階層上）に配置
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8008,
        reload=True
    )
