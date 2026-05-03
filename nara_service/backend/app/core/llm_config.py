from pydantic import BaseModel
from typing import Dict, Any

class OllamaSettings(BaseModel):
    """
    Ollama 모델 생성 옵션 설정
    서비스 품질에 직접적인 영향을 주는 핵심 파라미터들입니다.
    """
    model: str = "gemma3:1b"
    
    # 생성 옵션 (Ollama API options)
    options: Dict[str, Any] = {
        "num_ctx": 1536,      # 컨텍스트 윈도우 크기 (입력+출력 토큰 버퍼)
        "num_predict": 2048,  # 최대 생성 토큰 수 (응답 길이)
        "temperature": 0.7,   # 창의성/무작위성 조절 (0.0 ~ 1.0, 높을수록 창의적)
        "top_p": 0.9,         # Nucleus Sampling (상위 p% 확률의 토큰만 고려)
        "num_gpu": -1,        # GPU 가속 사용 (-1 = 자동 할당)
    }

llm_settings = OllamaSettings()
