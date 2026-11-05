// ---------------------------------------------------------------------
// GenreScreen: 장르별 대표 게임 둘러보기 화면
// 장르 버튼(칩)을 고르면 그 장르의 대표 게임 카드가 보이고,
// 카드를 누르면 상세 팝업이 열린다.
// 장르 목록은 화면에 들어올 때 한 번만 서버에서 받아오고,
// 장르를 바꿀 때는 이미 받아 둔 목록에서 골라 보여준다.
//
// 받는 정보(props)
//   onBack             : "처음으로" 버튼을 눌렀을 때 실행할 함수
//   onRecommendSimilar : 상세 팝업에서 "비슷한 게임 추천받기"를 눌렀을 때 실행할 함수
// ---------------------------------------------------------------------
import { useEffect, useState } from "react";
import { ArrowLeft, CircleAlert, Clock, Gauge, LoaderCircle } from "lucide-react";
import { getGenres } from "../api.js";
import { formatPlaytime } from "../format.js";
import { backButton, choiceClass } from "../styles.js";
import GameDetailModal from "../components/GameDetailModal.jsx";
import GameThumb from "../components/GameThumb.jsx";

export default function GenreScreen({ onBack, onRecommendSimilar }) {
  // 서버에서 받은 장르 목록 [{ key, label, description, games: [...] }, ...]
  const [genres, setGenres] = useState([]);
  // status: "loading" = 불러오는 중, "ok" = 성공, "error" = 실패
  const [status, setStatus] = useState("loading");
  // "다시 시도"를 누를 때마다 숫자를 올려서 다시 불러오게 함
  const [retry, setRetry] = useState(0);
  // 지금 고른 장르의 key (처음엔 첫 번째 장르)
  const [activeKey, setActiveKey] = useState("");
  // 상세 팝업으로 보고 있는 게임 ID (닫혀 있으면 null)
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    // ignore: 화면을 떠난 뒤 도착한 응답은 무시하기 위한 표시
    let ignore = false;
    getGenres()
      .then((data) => {
        if (ignore) return;
        setGenres(data);
        setStatus("ok");
      })
      .catch((err) => {
        if (ignore) return;
        console.error(err);
        setStatus("error");
      });
    return () => { ignore = true; };
  }, [retry]);

  // 고른 장르가 없거나 목록에 없으면 첫 번째 장르를 보여줌
  const active = genres.find((g) => g.key === activeKey) ?? genres[0];

  return (
    <div className="min-h-screen px-4 py-12">
      <main className="mx-auto max-w-3xl">
        <button type="button" onClick={onBack} className={backButton}>
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          처음으로
        </button>

        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight">장르별 대표 게임</h1>
          <p className="mt-2 text-ink/70">
            장르를 고르면 평점이 높은 대표 게임을 보여 드려요. 게임을 누르면 자세한 설명을 볼 수 있어요.
          </p>
        </header>

        {status === "loading" && (
          <p className="flex items-center justify-center gap-2 py-12 text-ink/60">
            <LoaderCircle className="h-5 w-5 motion-safe:animate-spin" aria-hidden="true" />
            장르 정보를 불러오는 중...
          </p>
        )}

        {status === "error" && (
          <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-danger">
            <p className="flex items-start gap-2">
              <CircleAlert className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              장르 정보를 불러오지 못했습니다. 서버가 켜져 있는지 확인해 주세요.
            </p>
            <button
              type="button"
              onClick={() => {
                setStatus("loading");
                setRetry((n) => n + 1);
              }}
              className="mt-2 text-sm underline"
            >
              다시 시도
            </button>
          </div>
        )}

        {status === "ok" && active && (
          <>
            {/* 장르 버튼(칩) 묶음 */}
            <div role="group" aria-label="장르 선택" className="flex flex-wrap gap-2">
              {genres.map((genre) => {
                const selected = genre.key === active.key;
                return (
                  <button
                    key={genre.key}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setActiveKey(genre.key)}
                    className={choiceClass(selected)}
                  >
                    {genre.label}
                  </button>
                );
              })}
            </div>

            {/* 고른 장르의 이름과 설명 */}
            <section className="mt-8" aria-live="polite">
              <h2 className="text-lg font-bold">
                {active.label}
                <span className="ml-2 text-sm font-normal text-ink/60">{active.description}</span>
              </h2>

              {/* 게임 카드 목록: 좁은 화면 2칸, 넓은 화면 3칸 */}
              <ul className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
                {active.games.map((game) => (
                  <li key={game.BGGId}>
                    <GameCard game={game} onSelect={setSelectedId} />
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </main>

      <GameDetailModal
        bggId={selectedId}
        onClose={() => setSelectedId(null)}
        onRecommendSimilar={onRecommendSimilar}
      />
    </div>
  );
}


// ---------------------------------------------------------------------
// GameCard: 장르 화면의 게임 카드 한 장 (누르면 상세 팝업)
// ---------------------------------------------------------------------
function GameCard({ game, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(game.BGGId)}
      aria-haspopup="dialog"
      className="group flex h-full w-full flex-col overflow-hidden rounded-xl border border-line bg-card text-left transition-colors hover:border-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-dark"
    >
      {/* aspect-square: 가로세로 같은 정사각형 */}
      <GameThumb src={game.ImagePath} className="aspect-square w-full" iconClassName="h-10 w-10" />
      <div className="flex flex-1 flex-col p-3">
        {/* line-clamp-2: 이름이 길면 2줄까지만 보여주고 "..." */}
        <h3 className="line-clamp-2 font-semibold leading-snug group-hover:underline">{game.Name}</h3>
        <p className="mt-auto flex flex-wrap gap-x-3 gap-y-1 pt-2 text-xs text-ink/60">
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            {formatPlaytime(game)}
          </span>
          <span className="inline-flex items-center gap-1">
            <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
            {(game.GameWeight ?? 0).toFixed(1)} / 5
          </span>
        </p>
      </div>
    </button>
  );
}
