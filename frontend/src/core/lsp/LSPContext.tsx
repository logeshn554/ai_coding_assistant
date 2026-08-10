/**
 * LSPContext.tsx
 * 
 * Manages the lifecycle of monaco-languageclient connections to the backend
 * LSP WebSocket proxy. One connection per language, lazy-opened when a file
 * of that language is first activated.
 *
 * Usage:
 *   const { isReady, connect, disconnect } = useLSP();
 *   connect('python');  // opens ws://host/ws/lsp/python
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
} from 'react';
// Monaco editor type (lazy import to avoid circular dep)
type MonacoEditor = any;

export interface LSPState {
  /** Current language with an active LSP connection, or null */
  activeLanguage: string | null;
  /** Whether the connection is healthy */
  isReady: boolean;
  /** Error message if the LS is unavailable */
  error: string | null;
  /** Connect to LSP for the given language */
  connect: (language: string, monacoInstance: MonacoEditor) => void;
  /** Tear down the current connection */
  disconnect: () => void;
}

const LSPContext = createContext<LSPState>({
  activeLanguage: null,
  isReady: false,
  error: null,
  connect: () => {},
  disconnect: () => {},
});

export function LSPProvider({ children }: { children: React.ReactNode }) {
  const [activeLanguage, setActiveLanguage] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Hold refs to active client and disposable
  const clientRef = useRef<any>(null);
  const disposeRef = useRef<(() => void) | null>(null);

  const disconnect = useCallback(() => {
    try {
      if (disposeRef.current) {
        disposeRef.current();
        disposeRef.current = null;
      }
      if (clientRef.current) {
        clientRef.current.stop?.();
        clientRef.current = null;
      }
    } catch (e) {
      console.warn('[LSP] Error during disconnect:', e);
    }
    setActiveLanguage(null);
    setIsReady(false);
    setError(null);
  }, []);

  const connect = useCallback(
    async (language: string, _monacoInstance: MonacoEditor) => {
      // Don't reconnect if already on the same language
      if (activeLanguage === language && isReady) return;

      // Tear down any existing connection
      disconnect();

      setActiveLanguage(language);
      setIsReady(false);
      setError(null);

      try {
        // Dynamic import to keep the main bundle slim — only loaded when LSP is first needed
        const { MonacoVscodeApiWrapper } = await import('monaco-languageclient/vscodeApiWrapper');
        await import('vscode/localExtensionHost');

        // Initialize VSCode API services if not already done
        const envEnhanced = (window as any).MonacoEnvironment;
        if (!envEnhanced || !envEnhanced.vscodeApiInitialised) {
          const wrapper = new MonacoVscodeApiWrapper({
            $type: 'classic',
            viewsConfig: {
              $type: 'EditorService'
            }
          });
          await wrapper.start({ caller: 'LSPContext' });
        }

        const { MonacoLanguageClient } = await import('monaco-languageclient');
        const { CloseAction, ErrorAction } = await import('vscode-languageclient/browser.js');

        const { toSocket, WebSocketMessageReader, WebSocketMessageWriter } = await import(
          'vscode-ws-jsonrpc'
        );

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/lsp/${language}`;

        const webSocket = new WebSocket(wsUrl);

        webSocket.onopen = async () => {
          const checkInitialError = (msg: MessageEvent) => {
            try {
              const data = JSON.parse(msg.data);
              if (data.error) {
                setError(data.error);
                setIsReady(false);
                webSocket.close();
                return;
              }
            } catch {
              // Normal LSP JSON-RPC frame — proceed
            }
            webSocket.removeEventListener("message", checkInitialError);
          };
          webSocket.addEventListener("message", checkInitialError);

          const socket = toSocket(webSocket);
          const reader = new WebSocketMessageReader(socket);
          const writer = new WebSocketMessageWriter(socket);

          const client = new MonacoLanguageClient({
            name: `DevPilot LSP (${language})`,
            clientOptions: {
              documentSelector: [
                { language: language === 'javascript' ? 'javascript' : language },
              ],
              errorHandler: {
                error: () => ({ action: ErrorAction.Continue }),
                closed: () => ({ action: CloseAction.DoNotRestart }),
              },
            },
            messageTransports: { reader, writer },
          });

          clientRef.current = client;
          disposeRef.current = () => {
            client.stop();
            reader.dispose();
            writer.dispose();
          };

          await client.start();
          setIsReady(true);
          console.info(`[LSP] Connected: ${language}`);
        };

        webSocket.onerror = () => {
          setError(`Could not connect to LSP server for ${language}. Make sure the backend is running.`);
          setIsReady(false);
        };

        webSocket.onclose = () => {
          if (isReady) {
            setIsReady(false);
          }
        };
      } catch (err: any) {
        const msg = err?.message || String(err);
        // If monaco-languageclient is not installed, degrade gracefully
        if (msg.includes('Cannot find module') || msg.includes('Failed to fetch')) {
          console.info('[LSP] monaco-languageclient not available — using Monaco built-in intellisense only.');
          setError('LSP packages not installed — using basic Monaco intellisense.');
        } else {
          setError(msg);
        }
        setIsReady(false);
      }
    },
    [activeLanguage, isReady, disconnect]
  );

  return (
    <LSPContext.Provider value={{ activeLanguage, isReady, error, connect, disconnect }}>
      {children}
    </LSPContext.Provider>
  );
}

export function useLSP(): LSPState {
  return useContext(LSPContext);
}
