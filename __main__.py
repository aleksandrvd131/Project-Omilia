import sys

sys.modules["sounddevice"] = None

import uvicorn


def main() -> None:
    uvicorn.run("project_omilia.serv:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
