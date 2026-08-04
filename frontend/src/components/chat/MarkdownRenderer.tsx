import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { CodeBlock } from './CodeBlock';

interface MarkdownRendererProps {
  content: string;
  onRunCommand?: (command: string) => void;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, onRunCommand }) => {
  return (
    <div className="prose prose-invert max-w-none text-[13.5px] leading-[1.65] text-zinc-300 font-sans">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          code: ({ className, children, ...props }) => {
            const isInline = !className && !String(children).includes('\n');
            return (
              <CodeBlock
                inline={isInline}
                className={className}
                onRunCommand={onRunCommand}
                {...props}
              >
                {children}
              </CodeBlock>
            );
          },
          p: ({ children }) => (
            <p className="mb-3.5 last:mb-0 leading-[1.65] text-[13px] text-zinc-300 select-text">
              {children}
            </p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-white">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="text-zinc-400 italic">{children}</em>
          ),
          h1: ({ children }) => (
            <h1 className="font-semibold text-zinc-100 mt-5 mb-3.5 pb-1 text-[15.5px] border-b border-zinc-800/80 flex items-center gap-2 select-text">
              <span className="text-green-500 font-bold">✓</span>
              <span>{children}</span>
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="font-semibold text-zinc-200 mt-4 mb-2 text-[14.5px] select-text">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="font-semibold text-zinc-300 mt-3 mb-1.5 text-[13.5px] select-text">
              {children}
            </h3>
          ),
          ul: ({ children }) => (
            <ul className="my-3 pl-0 space-y-2 text-[13px] text-zinc-300 list-none">
              {React.Children.map(children, (child) => {
                if (React.isValidElement(child)) {
                  return React.cloneElement(child, { isUlist: true } as any);
                }
                return child;
              })}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="my-3 pl-5 space-y-2 list-decimal text-[13px] text-zinc-300">
              {children}
            </ol>
          ),
          li: ({ children, ...props }: any) => {
            const isUlist = props.isUlist;
            if (isUlist) {
              return (
                <li className="leading-relaxed flex items-start gap-2.5 select-text">
                  <span className="text-green-500 font-black shrink-0 mt-0.5 select-none">✓</span>
                  <span className="flex-1">{children}</span>
                </li>
              );
            }
            return (
              <li className="leading-relaxed ml-4 pl-1 select-text">
                {children}
              </li>
            );
          },
          blockquote: ({ children }) => (
            <blockquote className="my-3.5 py-2 pl-4 border-l-2 border-blue-500/50 bg-blue-500/5 rounded-r-md text-zinc-400 italic">
              {children}
            </blockquote>
          ),
          hr: () => (
            <hr className="my-4.5 border-t border-zinc-800" />
          ),
          a: ({ href, children }) => {
            const isCodeFile = href?.toLowerCase().endsWith('.tsx') || href?.toLowerCase().endsWith('.ts') || href?.toLowerCase().endsWith('.js') || href?.toLowerCase().endsWith('.jsx');
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 underline underline-offset-2 transition-colors font-medium"
              >
                {isCodeFile && <span className="text-[10px] text-blue-400/90 shrink-0 font-sans">⚛</span>}
                <span>{children}</span>
              </a>
            );
          },
          table: ({ children }) => (
            <div className="overflow-x-auto my-4 rounded-lg border border-zinc-800">
              <table className="w-full text-[12.5px] border-collapse bg-zinc-950/40">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="text-left px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-zinc-400 bg-zinc-900 border-b border-zinc-800">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-1.5 border-b border-zinc-900 text-zinc-300">
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
