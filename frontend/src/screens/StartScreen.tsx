// ---------------------------------------------------------------------
// StartScreen: 맨 처음에 보이는 시작 화면
// 왼쪽은 제목과 버튼 두 개, 오른쪽은 사진 두 줄이 위에서 아래로 천천히 흐른다.
// 사진은 인원·시간 필터를 무작위로 골라 받은 게임들의 표지 사진이다 (api.ts의 getRandomPhotos).
//
// 받는 정보(props)
//   onNavigate : 버튼을 눌렀을 때 실행할 함수 (이동할 화면 이름을 넘겨줌)
// ---------------------------------------------------------------------
import clsx from "clsx";
import { useState } from "react";
import { Pause, Play } from "lucide-react";
import { useRandomPhotos } from "../queries";
import { container, focusRing, primaryButton, secondaryButton } from "../styles";
import type { Screen } from "../types";

interface StartScreenProps {
  onNavigate: (screen: Screen) => void;
}

// 사진 칸의 가로세로 비율 (1~6번째 사진)
const RATIOS = ["4 / 5", "1 / 1", "3 / 4", "1 / 1", "4 / 5", "3 / 4"];
const PHOTO_COUNT = 6;

export default function StartScreen({ onNavigate }: StartScreenProps) {
  // 무작위 사진 주소 6개 (불러오는 동안이나 실패하면 빈 칸으로 보임)
  const { data: sources = [] } = useRandomPhotos(PHOTO_COUNT);
  const photos = RATIOS.map((ratio, i) => ({ ratio, src: sources[i] ?? "" }));
  // 사진 흐름을 멈췄는지 (계속 움직이는 화면은 멈출 수 있어야 한다)
  const [paused, setPaused] = useState(false);

  const columns = [
    [photos[0], photos[2], photos[4]],
    [photos[1], photos[3], photos[5]],
  ];

  return (
    <main className={clsx(container, "flex flex-1 flex-wrap items-center gap-x-14 gap-y-8 py-7 sm:gap-y-12 sm:py-10")}>
      <div className="flex min-w-0 flex-[1_1_440px] flex-col gap-9">
        <h1 className="font-display text-[clamp(44px,7.4vw,96px)] leading-[0.96] font-extrabold tracking-[-0.03em]">
          Boardgame Recommender
        </h1>
        {/* 휴대폰(640px 미만)에서는 두 버튼이 반씩 나눠 한 줄에 나란히 서도록
            좌우 여백과 글자를 줄인다 (iPhone SE·13 mini의 375px 폭까지 한 줄) */}
        <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:gap-3">
          <button type="button" onClick={() => onNavigate("recommend")} className={clsx(primaryButton, HOME_BUTTON)}>
            Find similar games
          </button>
          <button type="button" onClick={() => onNavigate("genres")} className={clsx(secondaryButton, HOME_BUTTON)}>
            Browse by genre
          </button>
        </div>
      </div>

      <div
        className="relative h-110 min-w-0 flex-[1_1_420px] overflow-hidden rounded-3xl sm:h-175"
        style={{ maskImage: FADE_EDGES, WebkitMaskImage: FADE_EDGES }}
      >
        <div className="grid h-full grid-cols-2 gap-3.5" aria-hidden="true">
          {columns.map((column, c) => (
            <div key={c} className="min-w-0 overflow-hidden">
              {/* 같은 사진 목록을 두 번 이어 붙여 두고 절반만큼 내려가면 끊김 없이 반복된다 */}
              <div
                className="motion-safe:animate-drift-down"
                style={{
                  animationPlayState: paused ? "paused" : "running",
                  // 오른쪽 줄은 조금 더 느리게, 다른 위치에서 시작
                  ...(c === 1 ? { animationDuration: "60s", animationDelay: "-20s" } : {}),
                }}
              >
                {[...column, ...column].map((photo, i) => (
                  <PhotoTile key={`${i}-${photo.src}`} src={photo.src} ratio={photo.ratio} />
                ))}
              </div>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setPaused((p) => !p)}
          aria-label={paused ? "Play photos" : "Pause photos"}
          className={clsx("absolute right-4 bottom-4 inline-flex h-11 w-11 items-center justify-center rounded-full bg-card text-ink", focusRing)}
        >
          {paused ? (
            <Play className="h-4.5 w-4.5" fill="currentColor" aria-hidden="true" />
          ) : (
            <Pause className="h-4.5 w-4.5" fill="currentColor" aria-hidden="true" />
          )}
        </button>
      </div>
    </main>
  );
}

// 시작 화면 버튼: 휴대폰에서만 여백·글자를 줄인다
// (max-sm: 는 기본 버튼 스타일보다 나중에 적용되므로 px-8, text-[17px]을 덮어쓴다)
const HOME_BUTTON = "whitespace-nowrap max-sm:px-3 max-sm:text-[15px]";

// 사진 영역 위아래 끝을 부드럽게 흐리게
const FADE_EDGES = "linear-gradient(to bottom, transparent 0, #000 72px, #000 calc(100% - 72px), transparent 100%)";

// 사진 한 칸. 사진이 없거나 못 불러오면 빈 칸(선 색)으로 둔다.
function PhotoTile({ src, ratio }: { src: string; ratio: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="mb-3.5 overflow-hidden rounded-2xl bg-line" style={{ aspectRatio: ratio }}>
      {src && !failed && (
        <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} className="block h-full w-full object-cover" />
      )}
    </div>
  );
}
