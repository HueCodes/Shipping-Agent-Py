import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'flex w-full rounded-lg border border-border bg-bg-primary px-4 py-3',
          'text-base text-text-primary placeholder:text-text-dim',
          'focus:border-accent-blue focus:outline-none',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'transition-colors',
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)

Input.displayName = 'Input'

// Search input with icon
export const SearchInput = forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => {
    return (
      <div className="relative">
        <svg
          className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-dim"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          type="search"
          className={cn(
            'flex w-full rounded-lg border border-border bg-bg-primary py-2 pl-10 pr-4',
            'text-sm text-text-primary placeholder:text-text-dim',
            'focus:border-accent-blue focus:outline-none',
            'transition-colors',
            className
          )}
          ref={ref}
          {...props}
        />
      </div>
    )
  }
)

SearchInput.displayName = 'SearchInput'
