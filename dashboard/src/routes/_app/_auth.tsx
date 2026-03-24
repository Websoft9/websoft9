import { createFileRoute, Link, Outlet } from '@tanstack/react-router'

function AuthLayout() {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Protected routes layout - add auth checks here */}
      <header className="bg-white shadow-sm p-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Websoft9 Dashboard</h1>
        <nav className="flex gap-4">
          <Link
            to="/dashboard"
            className="text-gray-700 hover:text-blue-600"
            activeProps={{ className: 'font-bold text-blue-600' }}
          >
            Dashboard
          </Link>
          <Link
            to="/login"
            className="text-gray-700 hover:text-blue-600"
          >
            Logout
          </Link>
        </nav>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  )
}

export const Route = createFileRoute('/_app/_auth')({
  component: AuthLayout,
  // TODO: Add authentication check before loading
  // beforeLoad: async ({ context, location }) => {
  //   if (!context.auth.isAuthenticated) {
  //     throw redirect({ to: '/login', search: { redirect: location.href } })
  //   }
  // },
})
