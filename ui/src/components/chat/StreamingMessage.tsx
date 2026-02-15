import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { BotIcon, SparklesIcon } from '../icons'

interface StreamingMessageProps {
  text: string;
}

export function StreamingMessage({ text }: StreamingMessageProps) {
  if (!text) return null

  return (
    <div className="flex gap-3 px-4 py-4 animate-in slide-in-from-bottom-1 fade-in duration-200">
      {/* Avatar with sparkle animation */}
      <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 relative">
        <BotIcon size={16} />
        <span className="absolute -top-1 -right-1">
          <SparklesIcon size={10} className="text-primary animate-pulse" />
        </span>
      </div>
      
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-primary">Agent</span>
          <span className="text-xs text-muted-foreground">typing...</span>
        </div>
        
        {/* Content */}
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown
            components={{
              code(props) {
                const { children, className, ...rest } = props
                const match = /language-(\w+)/.exec(className || '')
                const codeString = String(children).replace(/\n$/, '')

                if (match) {
                  return (
                    <div className="relative group my-3">
                      <div className="flex items-center justify-between px-3 py-1.5 bg-muted/50 rounded-t-lg border-b border-border">
                        <span className="text-xs text-muted-foreground font-mono">{match[1]}</span>
                      </div>
                      <SyntaxHighlighter
                        style={oneDark}
                        language={match[1]}
                        PreTag="div"
                        className="rounded-b-lg text-sm !mt-0 !rounded-t-none"
                      >
                        {codeString}
                      </SyntaxHighlighter>
                      <button
                        onClick={() => navigator.clipboard.writeText(codeString)}
                        className="absolute top-8 right-2 opacity-0 group-hover:opacity-100
                                   px-2 py-1 rounded bg-white/10 text-white/70 text-xs
                                   hover:bg-white/20 transition-all duration-200"
                      >
                        Copy
                      </button>
                    </div>
                  )
                }
                return (
                  <code className="bg-muted/80 px-1.5 py-0.5 rounded text-sm font-mono text-primary/90" {...rest}>
                    {children}
                  </code>
                )
              },
              p({ children }) {
                return <p className="mb-3 last:mb-0 text-foreground/90">{children}</p>
              },
            }}
          >
            {text}
          </ReactMarkdown>
          {/* Cursor */}
          <span className="inline-block w-2 h-4 bg-primary/60 animate-pulse ml-0.5 rounded-sm" />
        </div>
      </div>
    </div>
  )
}
