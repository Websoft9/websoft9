import { createRootRoute, Link, Outlet } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/router-devtools'
import { ThemeProvider } from '@/components/theme-provider'
import { Button } from '@/components/ui/button'

function RootComponent() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="websoft9-ui-theme">
      <Outlet />
      {import.meta.env.DEV && <TanStackRouterDevtools />}
    </ThemeProvider>
  )
}

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background">
      <h1 className="text-6xl font-bold text-foreground mb-4">404</h1>
      <p className="text-xl text-muted-foreground mb-8">Page not found</p>
      <Button asChild>
        <Link to="/">Go Home</Link>
      </Button>
    </div>
  )
}

export const Route = createRootRoute({
  component: RootComponent,
  notFoundComponent: NotFound,
})
