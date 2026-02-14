import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface StreamingMessageProps {
  text: string;
}

export function StreamingMessage({ text }: StreamingMessageProps) {
  if (!text) return null

  return (
    <div className="flex gap-3 px-4 py-3">
      <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-bold shrink-0">
        A
      </div>
      <div className="flex-1 min-w-0 prose prose-sm dark:prose-invert max-w-none">
        <ReactMarkdown
          components={{
            code(props) {
              const { children, className, ...rest } = props
              const match = /language-(\w+)/.exec(className || '')
              const codeString = String(children).replace(/\n$/, '')

              if (match) {
                return (
                  <div className="relative group">
                    <SyntaxHighlighter
                      style={oneDark}
                      language={match[1]}
                      PreTag="div"
                      className="rounded-lg text-sm"
                    >
                      {codeString}
                    </SyntaxHighlighter>
                    <button
                      onClick={() => navigator.clipboard.writeText(codeString)}
                      className="absolute top-2 right-2 opacity-0 group-hover:opacity-100
                                 px-2 py-1 rounded bg-white/10 text-white/70 text-xs
                                 hover:bg-white/20 transition-opacity"
                    >
                      Copy
                    </button>
                  </div>
                )
              }
              return (
                <code className="bg-muted px-1.5 py-0.5 rounded text-sm" {...rest}>
                  {children}
                </code>
              )
            },
          }}
        >
          {text}
        </ReactMarkdown>
        <span className="inline-block w-2 h-4 bg-primary/60 animate-pulse ml-0.5" />
      </div>
    </div>
  )
}
