// ---------------------------------------------------------------------
// ErrorBoundary: 화면을 그리다 오류가 나도 빈 화면 대신 안내 문구를 보여 준다.
// (오류 경계는 클래스 컴포넌트로만 만들 수 있음)
// ---------------------------------------------------------------------
import { Component, type ReactNode } from "react";
import { noticeBox } from "../styles";

interface Props {
  children: ReactNode;
}

export default class ErrorBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="mx-auto w-full max-w-3xl px-4 py-10">
          <p role="alert" className={noticeBox}>
            Something went wrong. Please reload.
          </p>
        </main>
      );
    }
    return this.props.children;
  }
}
