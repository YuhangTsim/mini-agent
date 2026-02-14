import type { TodoItem } from '../../lib/api/types'

interface TodoPanelProps {
  items: TodoItem[];
}

export function TodoPanel({ items }: TodoPanelProps) {
  if (items.length === 0) return null

  const done = items.filter((i) => i.done).length
  const total = items.length

  return (
    <div className="border-t border-border p-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Todo List
        </h3>
        <span className="text-xs text-muted-foreground">
          {done}/{total}
        </span>
      </div>
      <div className="space-y-1">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-2 text-sm">
            <span className={`mt-0.5 ${item.done ? 'text-green-500' : 'text-muted-foreground'}`}>
              {item.done ? '[x]' : '[ ]'}
            </span>
            <span className={item.done ? 'line-through text-muted-foreground' : ''}>
              {item.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
