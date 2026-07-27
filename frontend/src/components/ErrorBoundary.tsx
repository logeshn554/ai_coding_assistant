import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
  title?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[ErrorBoundary caught error]:', error, errorInfo);
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  public render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error!, this.handleReset);
      }

      return (
        <div className="p-4 m-2 bg-red-950/40 border border-red-800/60 rounded-xl text-red-300 font-sans text-xs space-y-2 select-text">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-red-200 text-sm">
              {this.props.title || 'Component Error'}
            </h3>
            <button
              onClick={this.handleReset}
              className="px-2 py-0.5 rounded bg-red-900/60 hover:bg-red-800/80 text-red-100 text-[10px] font-semibold transition-colors cursor-pointer"
            >
              Retry
            </button>
          </div>
          <p className="text-red-300/80 font-mono text-[11px] leading-relaxed break-words">
            {this.state.error?.message || 'An unexpected error occurred in this view.'}
          </p>
        </div>
      );
    }

    return this.props.children;
  }
}
