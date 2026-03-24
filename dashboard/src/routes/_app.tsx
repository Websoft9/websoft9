import { createFileRoute, Outlet } from '@tanstack/react-router'

function AppLayout() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* App-level layout wrapper */}
      <Outlet />
    </div>
  )
}

export const Route = createFileRoute('/_app')({
  component: AppLayout,
})
