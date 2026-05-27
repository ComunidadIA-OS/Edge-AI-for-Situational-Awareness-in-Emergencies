"use client";

import { Component, Fragment, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

type Props = { children: ReactNode; fallback?: ReactNode };
type State = { error: Error | null; resetKey: number };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, resetKey: 0 };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  // Clearing the error AND bumping resetKey forces the keyed subtree below to
  // fully unmount/remount — without the key bump React reuses the broken
  // instances and the fallback flashes straight back.
  private handleRetry = () => {
    this.setState((s) => ({ error: null, resetKey: s.resetKey + 1 }));
  };

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="flex flex-col items-center justify-center gap-2 p-6 text-red-400">
            <AlertTriangle className="w-5 h-5" />
            <p className="text-sm font-medium">Unexpected error</p>
            <p className="text-xs text-zinc-500 text-center max-w-[180px]">
              {this.state.error.message}
            </p>
            <button
              onClick={this.handleRetry}
              className="text-xs text-zinc-400 hover:text-zinc-200 underline mt-1"
            >
              Retry
            </button>
          </div>
        )
      );
    }
    return <Fragment key={this.state.resetKey}>{this.props.children}</Fragment>;
  }
}
