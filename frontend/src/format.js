// =====================================================================
// format.js: 숫자나 글자를 화면에 보여주기 좋게 바꾸는 도우미 함수 모음
// =====================================================================

// 분 단위 숫자를 읽기 쉬운 글자로 바꿔주는 함수
// 예) 30 -> "30분", 60 -> "1시간", 90 -> "1시간 30분"
export function formatMinutes(min) {
  // 60분 미만이면 그냥 "○○분"
  if (min < 60) return `${min}분`;
  // Math.floor: 소수점 버리기. 90 / 60 = 1.5 -> 1
  const h = Math.floor(min / 60);
  // %: 나머지. 90 % 60 = 30
  const m = min % 60;
  // 나머지 분이 0이면 "1시간", 아니면 "1시간 30분"
  return m === 0 ? `${h}시간` : `${h}시간 ${m}분`;
}

// 단어 뒤에 "와" 또는 "과"를 알맞게 붙여주는 함수
// 마지막 글자에 받침이 있으면 "과", 없으면 "와"
// 예) 카탄 -> "카탄과", 스플렌더 -> "스플렌더와"
export function withWa(word) {
  // 마지막 글자의 유니코드 번호를 가져옴
  const code = word.charCodeAt(word.length - 1);
  // 한글(가~힣)이 아니면 판단할 수 없으니 "와(과)"로 처리
  if (code < 0xac00 || code > 0xd7a3) return `${word}와(과)`;
  // 한글 번호를 28로 나눈 나머지가 0이면 받침이 없는 글자
  return (code - 0xac00) % 28 === 0 ? `${word}와` : `${word}과`;
}

// 게임의 플레이 시간 글자 만들기
// 실제 데이터의 누락·잘못된 시간 범위는 숫자 대신 안내
// 최소·최대가 같으면 "30분", 다르면 "30~45분"
export function formatPlaytime(game) {
  const min = game.ComMinPlaytime;
  const max = game.ComMaxPlaytime;
  if (!(min > 0 && max >= min)) return "시간 정보 없음";
  return min === max ? `${max}분` : `${min}~${max}분`;
}

// 인원 글자 만들기. 예) 2~4명, 같으면 "2명"
export function formatPlayers(game) {
  const { MinPlayers: min, MaxPlayers: max } = game;
  if (!(min > 0 && max >= min)) return "인원 정보 없음";
  return min === max ? `${min}명` : `${min}~${max}명`;
}

// 게임 설명에 들어 있는 &quot; &#10; 같은 HTML 엔티티를 원래 글자로 바꾸는 함수
// DOMParser는 글자를 해석만 하고 화면에 넣지 않으므로, 설명 속 태그나 스크립트가 실행되지 않는다.
// 결과는 textContent(순수 글자)만 꺼내서 쓴다.
export function decodeEntities(text) {
  if (!text) return "";
  const doc = new DOMParser().parseFromString(text.replace(/</g, "&lt;"), "text/html");
  return doc.documentElement.textContent ?? "";
}
