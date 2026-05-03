def get_system_prompt():
    return """당신은 공공데이터 포털의 AI 어시스턴트입니다.
사용자의 질문에 대해 제공된 컨텍스트를 바탕으로 정확하고 도움이 되는 답변을 제공하세요.
답변은 한국어로 작성하며, 친절하고 전문적인 톤을 유지하세요.
컨텍스트에 없는 정보는 추측하지 말고, 컨텍스트 내의 정보만 사용하세요."""

def get_user_prompt(context_text, query):
    return f"""다음은 관련된 공공데이터 정보입니다:

{context_text}

사용자 질문: {query}

위 정보를 바탕으로 사용자의 질문에 답변해주세요. 관련 URL이나 추가 정보도 함께 제공하면 좋습니다."""

def get_ollama_prompt(context_text, query):
    return f"""공공데이터 정보:

{context_text}

질문: {query}

위 정보만 사용해 한국어로 답변하세요."""
