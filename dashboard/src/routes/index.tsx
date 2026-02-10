import { createFileRoute, Link } from '@tanstack/react-router'
import { ModeToggle } from '@/components/mode-toggle'

function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background">
      {/* Temporary theme toggle for testing - will be moved to Header in Story 7.6 */}
      <div className="fixed top-4 right-4">
        <ModeToggle />
      </div>
      <h1 className="text-4xl font-bold mb-4 text-foreground">Welcome to Websoft9 Dashboard</h1>
      <p className="text-lg text-muted-foreground mb-8">Your unified management platform</p>
      <div className="flex gap-4">
        <Link
          to="/login"
          className="px-6 py-3 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
        >
          Login
        </Link>
        <Link
          to="/dashboard"
          className="px-6 py-3 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors"
        >
          Dashboard
        </Link>
      </div>
    </div>
  )
}

export const Route = createFileRoute('/')({
  component: HomePage,
})
