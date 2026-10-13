import os
import traceback

from langchain.chat_models import BaseChatModel, init_chat_model
from pydantic import SecretStr

from zixuetong import config
from zixuetong.services.model_cache import is_v2_spec_format
from zixuetong.utils import get_docker_safe_url
from zixuetong.utils.logging_config import logger


def load_chat_model_v2(spec: str, enable_thinking: bool | None = None, **kwargs) -> BaseChatModel:
    """根据 v2 spec（provider_id:model_id）加载 LangChain 聊天模型。

    v2 spec 格式使用冒号分隔，如: siliconflow-cn:deepseek-ai/DeepSeek-V4-Flash
    数据来源为数据库中的 model_providers 表，通过全局缓存访问。

    Args:
        spec: v2 模型 spec。
        enable_thinking: 是否开启模型思考（推理过程）。None 表示不干预，
            由服务端默认行为决定；True/False 会以 enable_thinking 透传给
            OpenAI 兼容服务。
        **kwargs: 透传给底层 LangChain 模型构造函数的额外参数。
    """
    from zixuetong.services.model_cache import model_cache

    info = model_cache.get_model_info(spec)
    if not info:
        raise ValueError(f"Unknown v2 model spec: {spec}")

    if info.model_type != "chat":
        raise ValueError(f"Model {spec} is not a chat model (type={info.model_type})")

    api_key = info.api_key
    base_url = get_docker_safe_url(info.base_url)

    logger.debug(f"[v2] Loading model {spec} with provider_type={info.provider_type}")

    # 根据 provider_type 选择合适的 LangChain 模型
    if info.provider_type == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=info.model_id,
            api_key=SecretStr(api_key),
            base_url=base_url,
            **kwargs,
        )
    elif info.provider_type == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=info.model_id,
            google_api_key=SecretStr(api_key),
            **kwargs,
        )
    else:
        # 默认使用 OpenAI 兼容层（openai, openrouter, ollama, lmstudio 等）。
        # 使用 ChatOpenAIWithReasoning 以保留第三方服务返回的 reasoning_content，
        # 标准 ChatOpenAI 会丢弃该非标准字段。
        from zixuetong.agents.chat_models import ChatOpenAIWithReasoning

        if enable_thinking is not None:
            extra_body = dict(kwargs.pop("extra_body", None) or {})
            extra_body["enable_thinking"] = bool(enable_thinking)
            kwargs["extra_body"] = extra_body

        return ChatOpenAIWithReasoning(
            model=info.model_id,
            api_key=SecretStr(api_key),
            base_url=base_url,
            stream_usage=True,
            **kwargs,
        )


def load_chat_model(fully_specified_name: str, **kwargs) -> BaseChatModel:
    """
    Load a chat model from a fully specified name.
    """
    # v2 判断：第一个特殊字符为冒号则走 v2 路径
    if is_v2_spec_format(fully_specified_name):
        from zixuetong.services.model_cache import model_cache

        info = model_cache.get_model_info(fully_specified_name)
        if info:
            return load_chat_model_v2(fully_specified_name, **kwargs)

        # 缓存均未命中，报错并列出可用模型
        available_specs = model_cache.get_all_specs("chat")
        available_ids = [s.spec for s in available_specs[:10]]
        raise ValueError(
            f"Unknown v2 model spec: '{fully_specified_name}'. "
            f"Available chat models ({len(available_specs)}): {available_ids}"
        )

    logger.warning(f"旧版本的模型选择逻辑已废弃，建议尽快迁移至新的模型配置；当前模型选择参数: {fully_specified_name=}")

    # v1 逻辑：spec 必须包含 /
    if "/" not in fully_specified_name:
        raise ValueError(
            f"Invalid model spec: '{fully_specified_name}'. "
            f"v1 format requires 'provider/model_name', v2 format requires 'provider_id:model_id'"
        )

    provider, model = fully_specified_name.split("/", maxsplit=1)

    assert provider != "custom", "[弃用] 自定义模型已移除，请在 zixuetong/config/static/models.py 中配置"

    model_info = config.model_names.get(provider)
    if not model_info:
        raise ValueError(f"Unknown model provider: {provider}")

    env_var = model_info.env

    api_key = os.getenv(env_var) or env_var

    base_url = get_docker_safe_url(model_info.base_url)

    if provider in ["openai", "deepseek"]:
        model_spec = f"{provider}:{model}"
        logger.debug(f"[offical] Loading model {model_spec} with kwargs {kwargs}")
        return init_chat_model(model_spec, **kwargs)

    elif provider in ["dashscope"]:
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(
            model=model,
            api_key=SecretStr(api_key),
            base_url=base_url,
            api_base=base_url,
            stream_usage=True,
        )

    else:
        try:  # 其他模型，默认使用 OpenAI 兼容层, like openai, zhipuai
            from zixuetong.agents.chat_models import ChatOpenAIWithReasoning

            return ChatOpenAIWithReasoning(
                model=model,
                api_key=SecretStr(api_key),
                base_url=base_url,
                stream_usage=True,
            )
        except Exception as e:
            raise ValueError(f"Model provider {provider} load failed, {e} \n {traceback.format_exc()}")
