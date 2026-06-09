from dotenv import load_dotenv

load_dotenv(".env", override=True)

from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from importlib import import_module  # noqa: E402

from zixuetong.config import config as config  # noqa: E402

try:
    from importlib.metadata import version

    __version__ = version("zixuetong")
except Exception:
    __version__ = "unknown"

executor = ThreadPoolExecutor()  # noqa: E402


def get_version():
    """Return the 自学通 version."""
    return __version__


def __getattr__(name: str):
    if name in {"graph_base", "knowledge_base"}:
        knowledge = import_module("zixuetong.knowledge")
        return getattr(knowledge, name)
    raise AttributeError(f"module 'zixuetong' has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | {"graph_base", "knowledge_base"})
