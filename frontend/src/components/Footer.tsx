// ---------------------------------------------------------------------
// Footer: 모든 화면 맨 아래에 붙는 푸터
// 게임 정보와 표지 사진은 BoardGameGeek(BGG) 데이터라서,
// BGG XML API 이용 약관에 따라 BGG로 연결되는 "Powered by BGG" 로고를 보여 준다.
// 로고 파일: public/powered-by-bgg.webp (BGG가 제공하는 공식 로고)
// ---------------------------------------------------------------------
import clsx from "clsx";
import { container, focusRing } from "../styles";

export default function Footer() {
  return (
    <footer className="border-t border-line bg-card">
      <div className={clsx(container, "flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-5")}>
        <p className="text-sm text-ink/70">Game data and images from BoardGameGeek.</p>
        <a
          href="https://boardgamegeek.com/"
          target="_blank"
          rel="noopener noreferrer"
          className={clsx("inline-flex rounded-md", focusRing)}
        >
          {/* width·height는 원본 크기. 사진을 받기 전에도 자리를 잡아 두어 화면이 덜컹거리지 않게 한다 */}
          <img src="/powered-by-bgg.webp" alt="Powered by BGG" width={900} height={264} className="h-8 w-auto" />
        </a>
      </div>
    </footer>
  );
}
