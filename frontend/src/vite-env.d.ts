/// <reference types="vite/client" />

// .env 파일에 넣는 VITE_ 환경변수 목록 (.env.example 참고)
interface ImportMetaEnv {
  readonly VITE_BASE_URL?: string;  // 배포된 백엔드 주소 (끝에 / 없이)
  readonly VITE_API_URL?: string;   // 예전 이름. VITE_BASE_URL이 없을 때만 사용
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
