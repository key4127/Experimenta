from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import logging

from .base import BaseLLM
from .huggingface_llm import HuggingFaceLLM
from .deepseek_llm import DeepSeekLLM

logger = logging.getLogger(__name__)

class LLMFactory:
    """Factory class for creating LLM instances."""
    
    @staticmethod
    def create_llm(config: Dict[str, Any]) -> BaseLLM:
        """Create an LLM instance based on configuration.
        
        Args:
            config: Configuration dictionary containing LLM settings
            
        Returns:
            An instance of BaseLLM
            
        Raises:
            ValueError: If the LLM type is not supported
        """
        llm_type = config["type"].lower()
        model = config.get("model")
        
        if not model:
            raise ValueError("Model must be specified in the config file")
        
        # Extract rate limit settings from config
        # First check if there are specific rate limits in the LLM config
        rate_limits = config.get("rate_limits", {})
        
        # If not, check if there are global rate limits for this provider type
        global_config = LLMFactory.load_config()
        if not rate_limits and "rate_limits" in global_config:
            # Map LLM types to provider names in rate_limits section
            provider_map = {
                "openai": "openai",
                "claude": "claude",
                "gemini": "gemini",
                "deepseek": "deepseek",
            }
            provider_key = provider_map.get(llm_type, llm_type)
            provider_limits = global_config.get("rate_limits", {}).get(provider_key, {})
            if provider_limits:
                rate_limits = provider_limits
        
        if llm_type == "huggingface":
            return HuggingFaceLLM(
                model_name=model,
                device=config.get("device", "cuda"),
                torch_dtype=config.get("torch_dtype", "float16")
            )
        if llm_type == "deepseek":
            api_key = config.get("api_key") or ""
            if not api_key:
                raise ValueError("DeepSeek config must include api_key")
            return DeepSeekLLM(
                model_name=model,
                api_key=api_key,
                api_base=config.get("api_base", "https://api.deepseek.com"),
            )
        raise ValueError(f"Unsupported LLM type: {llm_type}")
    
    @staticmethod
    def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load LLM configuration from file.
        
        Args:
            config_path: Path to the configuration file. If None, uses default path.
            
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
        """
        # 项目根目录（从 factory.py 的位置推断：experimenta/agent/llm/factory.py -> 项目根目录）
        project_root = Path(__file__).parent.parent.parent.parent
        
        if config_path is None:
            config_path = str(project_root / "config" / "docs_agent.yaml")
        else:
            # 处理相对路径
            config_path_obj = Path(config_path)
            if not config_path_obj.is_absolute():
                # 相对路径：相对于项目根目录
                config_path = str(project_root / config_path)
            else:
                config_path = str(config_path_obj)
        
        config_path_obj = Path(config_path)
        
        # 如果指定的配置文件不存在，尝试后备配置
        if not config_path_obj.exists():
            # 如果请求的是 agent_config.yaml 但不存在，尝试 docs_agent.yaml
            if config_path.endswith("agent_config.yaml"):
                fallback_path = project_root / "config" / "docs_agent.yaml"
                if fallback_path.exists():
                    logger.warning(f"配置文件 {config_path} 不存在，使用后备配置 {fallback_path}")
                    config_path = str(fallback_path)
                    config_path_obj = fallback_path
        
        if not config_path_obj.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        return config 