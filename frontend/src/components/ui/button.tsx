import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'primary' | 'ghost' | 'destructive'
  size?: 'sm' | 'md' | 'lg'
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={cn(
          'inline-flex items-center justify-center rounded-md font-medium transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-blue',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          {
            // Variants
            'bg-transparent border border-border text-text-muted hover:bg-bg-tertiary hover:text-text-secondary':
              variant === 'default',
            'bg-accent-blue text-white border-none hover:bg-accent-blue-hover':
              variant === 'primary',
            'bg-transparent border-none text-text-muted hover:bg-bg-tertiary hover:text-text-secondary':
              variant === 'ghost',
            'bg-accent-red text-white border-none hover:bg-red-600':
              variant === 'destructive',
            // Sizes
            'px-3 py-1.5 text-sm': size === 'sm',
            'px-4 py-2 text-sm': size === 'md',
            'px-6 py-3 text-base': size === 'lg',
          },
          className
        )}
        {...props}
      />
    )
  }
)

Button.displayName = 'Button'
