from __future__ import annotations

import uvicorn

from nvh_web_backend import config
from nvh_web_backend.app import create_app


def main() -> None:
    uvicorn.run(create_app(), host=config.host(), port=config.port())


if __name__ == "__main__":
    main()
