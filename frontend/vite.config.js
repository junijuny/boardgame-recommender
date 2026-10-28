import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // 백엔드 CORS 허용 주소와 맞춤. 사용 중이면 다른 포트로 바꾸지 않고 안내
  server: { port: 5173, strictPort: true },
});
