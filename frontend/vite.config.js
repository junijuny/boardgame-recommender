import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  // .env 의 배포된 백엔드 주소 (api.ts와 같은 규칙: VITE_BASE_URL, 없으면 예전 이름 VITE_API_URL)
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const backend = (env.VITE_BASE_URL || env.VITE_API_URL || "").replace(/\/+$/, "");

  return {
    plugins: [react(), tailwindcss()],
    server: {
      // 백엔드 CORS 허용 주소와 맞춤. 사용 중이면 다른 포트로 바꾸지 않고 안내
      port: 5173,
      strictPort: true,
      // 개발 중에는 /api 로 보낸 요청을 개발 서버가 배포된 백엔드로 대신 전달한다.
      // 배포된 백엔드가 localhost를 CORS로 허용하지 않아도 로컬에서 바로 쓸 수 있다.
      // (빌드한 배포 화면은 프록시 없이 백엔드 주소로 직접 요청)
      proxy: backend
        ? {
            "/api": {
              target: backend,
              changeOrigin: true,
              rewrite: (path) => path.replace(/^\/api/, ""),
            },
          }
        : undefined,
    },
  };
});
