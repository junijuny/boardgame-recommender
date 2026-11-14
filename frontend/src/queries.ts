// =====================================================================
// queries.ts: 화면에서 쓰는 서버 데이터 훅 모음 (TanStack Query)
// 화면 코드는 api.ts 함수를 직접 부르지 않고 여기 있는 훅을 쓴다.
//
// TanStack Query 상태 읽는 법
//   isPending  : 아직 데이터가 한 번도 없음 (처음 불러오는 중) -> 로딩 뼈대
//   isFetching : 지금 서버에 요청 중 (데이터가 있어도 true)  -> 다시 불러오는 중 막대
//   isError    : 실패 (error에 axios 에러가 들어 있음)
// =====================================================================

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  errorResponse, explain, getGameDetail, getGenres, getOtherGenreGames, getRandomPhotos, getServerInfo, naturalSearch,
  recommend, searchGames,
} from "./api";
import type { ExplainRequest } from "./types";

// 장르 8개와 장르별 대표 게임 (서버가 켜질 때 한 번 계산되므로 다시 불러올 필요 없음)
export function useGenres() {
  return useQuery({
    queryKey: ["genres"],
    queryFn: getGenres,
    staleTime: Infinity,
  });
}

// 게임 한 개의 상세 정보. bggId가 null이면 요청하지 않는다.
export function useGameDetail(bggId: number | null) {
  return useQuery({
    queryKey: ["game", bggId],
    queryFn: ({ signal }) => getGameDetail(bggId!, signal),
    enabled: bggId != null,
    // 없는 게임(404)은 다시 시도해도 같으니 바로 실패로 처리
    retry: (count, err) => errorResponse(err)?.status !== 404 && count < 1,
  });
}

// 게임 이름 검색. 2글자 이상이고 enabled일 때만 요청한다.
// 검색어가 바뀌면 TanStack Query가 이전 요청을 signal로 취소한다.
export function useGameSearch(term: string, enabled: boolean) {
  return useQuery({
    queryKey: ["search", term],
    queryFn: ({ signal }) => searchGames(term, signal),
    enabled: enabled && term.length >= 2,
  });
}

// 시작 화면의 무작위 게임 사진 count장
// 한 번 고른 사진은 페이지를 새로 열 때까지 그대로 둔다 (화면을 오갈 때마다 바뀌지 않게)
export function useRandomPhotos(count: number) {
  return useQuery({
    queryKey: ["random-photos", count],
    queryFn: ({ signal }) => getRandomPhotos(count, signal),
    staleTime: Infinity,
  });
}

// 장르 새로고침: 이미 본 게임을 빼고 같은 장르의 다른 게임 받기
// (버튼을 누를 때만 요청하므로 useMutation 사용)
export function useGenreRefresh() {
  return useMutation({
    mutationFn: ({ key, exclude }: { key: string; exclude: number[] }) => getOtherGenreGames(key, exclude),
  });
}

// 비슷한 게임 추천 (POST 요청이라 useMutation 사용)
export function useRecommend() {
  return useMutation({ mutationFn: recommend });
}

// 서버 정보 (자연어 검색·추천 이유 기능이 켜져 있는지). 한 번만 불러온다.
export function useServerInfo() {
  return useQuery({
    queryKey: ["server-info"],
    queryFn: getServerInfo,
    staleTime: Infinity,
    retry: 1,
  });
}

// 자연어 검색 (POST 요청이라 useMutation 사용)
export function useNaturalSearch() {
  return useMutation({ mutationFn: naturalSearch });
}

// 결과 게임들의 한 문장 추천 이유. req가 null이면 요청하지 않는다.
// 같은 요청은 다시 보내지 않는다 (staleTime: Infinity). 실패해도 재시도 없이 조용히 넘어간다.
export function useExplanations(req: ExplainRequest | null) {
  return useQuery({
    queryKey: ["explain", req?.mode, req?.basis, ...(req?.game_ids ?? [])],
    queryFn: () => explain(req!),
    enabled: req != null,
    staleTime: Infinity,
    retry: false,
  });
}

// 값이 delay(ms) 동안 바뀌지 않아야 그 값을 돌려준다 (검색어 입력 지연용)
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

// 로딩이 after(ms)보다 오래 걸리고 있는지 (배포 서버가 잠에서 깨는 중일 때 안내용)
// 배포 서버는 15분간 요청이 없으면 잠들고, 깨어나는 데 최대 1분쯤 걸린다.
export function useIsSlow(loading: boolean, after = 4000): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!loading) return;
    const timer = setTimeout(() => setSlow(true), after);
    return () => {
      clearTimeout(timer);
      setSlow(false);
    };
  }, [loading, after]);
  return loading && slow;
}
