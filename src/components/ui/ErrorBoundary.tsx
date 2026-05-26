"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

type Props = { children: ReactNode; fallback?: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

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
              onClick={() => this.setState({ error: null })}
              className="text-xs text-zinc-400 hover:text-zinc-200 underline mt-1"
            >
              Retry
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
