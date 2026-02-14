import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import type { Message } from '../../lib/api/types'

interface MessageListProps {
  messages: Message[];
  children?: React.ReactNode; // For streaming message / tool calls at the end
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? 'bg-muted/30' : ''}`}>
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
          isUser
            ? 'bg-secondary text-secondary-foreground'
            : 'bg-primary/10 text-primary'
        }`}
      >
        {isUser ? 'U' : 'A'}
      </div>
      <div className="flex-1 min-w-0 prose prose-sm dark:prose-invert max-w-none">
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
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
            {message.content}
          </ReactMarkdown>
        )}
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
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        {messages.length === 0 && !children && (
          <div className="flex items-center justify-center h-full min-h-[300px] text-muted-foreground">
            <p>Send a message to start a conversation</p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {children}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
