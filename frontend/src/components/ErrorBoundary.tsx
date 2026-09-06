import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center w-full h-full min-h-[300px] p-6 bg-[#070a12] text-slate-200 border border-red-500/20 rounded-lg">
          <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center mb-4 text-red-400">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold font-mono uppercase tracking-wider text-red-300 mb-1">
            {this.props.fallbackTitle || 'Component Rendering Error'}
          </h3>
          <p className="text-xs text-slate-400 font-mono mb-4 text-center max-w-md">
            {this.state.error?.message || 'An unexpected error occurred during rendering.'}
          </p>

          {this.state.error?.stack && (
            <div className="w-full max-w-lg mb-4 bg-black/50 border border-white/10 rounded p-3 text-[10px] font-mono text-slate-400 overflow-auto max-h-36">
              {this.state.error.stack}
            </div>
          )}

          <button
            onClick={this.handleReset}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-red-500/20 border border-red-500/40 text-red-300 hover:bg-red-500/30 text-xs font-mono transition-colors cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>RELOAD COCKPIT</span>
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
