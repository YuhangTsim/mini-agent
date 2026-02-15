import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { BotIcon, UserIcon } from '../icons'
import type { Message } from '../../lib/api/types'

interface MessageListProps {
  messages: Message[];
  children?: React.ReactNode;
}

function formatTime(dateStr: string) {
  const date = new Date(dateStr)
  return date.toLocaleTimeString('en-US', { 
    hour: 'numeric', 
    minute: '2-digit',
    hour12: true 
  })
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div 
      className={`flex gap-3 px-4 py-4 animate-in slide-in-from-bottom-2 fade-in duration-300 ${
        isUser ? 'bg-secondary/30' : 'bg-background'
      }`}
    >
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-transform hover:scale-105 ${
          isUser
            ? 'bg-secondary text-secondary-foreground'
            : 'bg-primary/10 text-primary'
        }`}
      >
        {isUser ? <UserIcon size={16} /> : <BotIcon size={16} />}
      </div>
      
      {/* Content */}
      <div className="flex-1 min-w-0">
        {/* Header with role and time */}
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-sm font-medium ${isUser ? 'text-foreground' : 'text-primary'}`}>
            {isUser ? 'You' : 'Agent'}
          </span>
          <span className="text-xs text-muted-foreground">
            {formatTime(message.created_at)}
          </span>
        </div>
        
        {/* Message content */}
        <div className="prose prose-sm dark:prose-invert max-w-none">
          {isUser ? (
            <p className="whitespace-pre-wrap text-foreground/90">{message.content}</p>
          ) : (
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
                ul({ children }) {
                  return <ul className="mb-3 last:mb-0 space-y-1">{children}</ul>
                },
                ol({ children }) {
                  return <ol className="mb-3 last:mb-0 space-y-1">{children}</ol>
                },
                li({ children }) {
                  return <li className="text-foreground/90">{children}</li>
                },
                h1({ children }) {
                  return <h1 className="text-lg font-semibold mb-3 text-foreground">{children}</h1>
                },
                h2({ children }) {
                  return <h2 className="text-base font-semibold mb-2 mt-4 text-foreground">{children}</h2>
                },
                h3({ children }) {
                  return <h3 className="text-sm font-semibold mb-2 mt-3 text-foreground">{children}</h3>
                },
                blockquote({ children }) {
                  return <blockquote className="border-l-2 border-primary/30 pl-3 italic text-muted-foreground my-3">{children}</blockquote>
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
        </div>
      </div>
    </div>
  )
}

export function MessageList({ messages, children }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, children])

  return (
    <div className="flex-1 overflow-y-auto scroll-smooth">
      <div className="max-w-4xl mx-auto">
        {messages.length === 0 && !children && (
          <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-muted-foreground">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <BotIcon size={32} className="text-primary" />
            </div>
            <p className="text-lg font-medium text-foreground">Ready to help</p>
            <p className="text-sm mt-1">Send a message to start a conversation</p>
          </div>
        )}

        <div className="divide-y divide-border/50">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
        </div>

        {children}

        <div ref={bottomRef} className="h-4" />
      </div>
    </div>
  )
}
