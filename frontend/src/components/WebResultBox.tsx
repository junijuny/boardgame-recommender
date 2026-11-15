// ---------------------------------------------------------------------
// WebResultBox: 웹 검색(Google 근거)이 쓰인 검색의 요약과 Google 검색어 추천 위젯.
// 약관상 추천 위젯 HTML은 고치지 않고 그대로, 샌드박스 iframe 안에 보여 준다.
// 칩 링크가 iframe 안에서 열리면 google.com이 거부하므로, 우리 문서로 감싸 새 탭(<base target>)으로 연다.
// 요약은 HTML이 아니라 글자로만 그린다. 이 내용은 어디에도 저장하지 않는다.
//
// 받는 정보(props)
//   web : 서버가 준 { summary, suggestions_html }
// ---------------------------------------------------------------------
import clsx from "clsx";
import { noticeBox } from "../styles";
import type { WebResult } from "../types";

// 위젯 HTML은 한 글자도 바꾸지 않고 body 안에 그대로 넣는다
function suggestionsDocument(html: string) {
  return `<!doctype html><html><head><meta charset="utf-8"><base target="_blank"></head><body style="margin:0">${html}</body></html>`;
}

export default function WebResultBox({ web }: { web: WebResult }) {
  return (
    <section aria-label="From the web" className={clsx(noticeBox, "flex min-w-0 flex-col gap-2 text-ink")}>
      <h3 className="font-bold">From the web</h3>
      {web.summary.trim() && <p className="break-words text-[15px] text-ink/80">{web.summary}</p>}
      <iframe
        sandbox="allow-popups allow-popups-to-escape-sandbox"
        srcDoc={suggestionsDocument(web.suggestions_html)}
        title="Google search suggestions"
        className="h-16 min-h-16 w-full max-w-full border-0"
      />
    </section>
  );
}
