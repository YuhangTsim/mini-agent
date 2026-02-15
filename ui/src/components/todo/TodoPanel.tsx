import { ListTodoIcon, CircleCheckIcon, CircleIcon } from '../icons'
import type { TodoItem } from '../../lib/api/types'

interface TodoPanelProps {
  items: TodoItem[];
}

export function TodoPanel({ items }: TodoPanelProps) {
  if (items.length === 0) return null

  const done = items.filter((i) => i.done).length
  const total = items.length
  const progress = Math.round((done / total) * 100)

  return (
    <div className="border-t border-border bg-card">
      {/* Header with progress */}
      <div className="px-3 py-3 border-b border-border/50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <ListTodoIcon size={14} className="text-primary" />
            <h3 className="text-xs font-semibold text-foreground uppercase tracking-wide">
              Tasks
            </h3>
          </div>
          <span className="text-xs font-medium text-muted-foreground">
            {done}/{total}
          </span>
        </div>
        
        {/* Progress bar */}
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div 
            className="h-full bg-primary transition-all duration-500 ease-out rounded-full"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Task list */}
      <div className="p-2 space-y-0.5 max-h-48 overflow-y-auto">
        {items.map((item, i) => (
          <div 
            key={i} 
            className={`flex items-start gap-2 px-2 py-1.5 rounded-md text-sm transition-colors ${
              item.done ? 'opacity-60' : 'hover:bg-muted/50'
            }`}
          >
            <span className={`mt-0.5 shrink-0 transition-colors ${
              item.done ? 'text-emerald-400' : 'text-muted-foreground'
            }`}>
              {item.done ? <CircleCheckIcon size={14} /> : <CircleIcon size={14} />}
            </span>
            <span className={`leading-relaxed ${
              item.done ? 'line-through text-muted-foreground' : 'text-foreground/90'
            }`}>
              {item.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
