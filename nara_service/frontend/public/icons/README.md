# Icons Directory

이 폴더에는 LLM 로고 이미지 파일이 저장되어 있습니다.

## 현재 파일 목록:
- `chatgpt.png` - ChatGPT/OpenAI 로고 (PNG 형식)
- `ollama.svg` - Ollama 로고 (SVG 형식)

## 사용 위치

### QuerySection 컴포넌트
`src/components/QuerySection.tsx`에서 LLM 선택 라디오 버튼에 사용됩니다.

```tsx
// Image 컴포넌트 사용 예시
import Image from "next/image";

<Image
  src="/icons/chatgpt.png"
  alt="ChatGPT"
  width={16}
  height={16}
  className="mr-2"
/>

<Image
  src="/icons/ollama.svg"
  alt="Ollama"
  width={16}
  height={16}
  className="mr-2"
/>
```

## 파일 형식

### PNG vs SVG
- **chatgpt.png**: PNG 형식으로 제공 (비트맵 이미지)
- **ollama.svg**: SVG 형식으로 제공 (벡터 이미지, 확대/축소 시 품질 유지)

## 권장 사양
- **PNG**: 투명 배경 권장, 최소 48x48px (Retina 디스플레이 대응)
- **SVG**: 벡터 형식으로 모든 크기에서 선명하게 표시
- **색상**: 브랜드 공식 색상 사용
- **다크 모드**: 다크 모드에서도 잘 보이도록 색상 고려

## 새 아이콘 추가 시
1. 파일을 이 폴더에 복사
2. `QuerySection.tsx`에서 import 및 사용
3. 적절한 alt 텍스트 제공 (접근성)
