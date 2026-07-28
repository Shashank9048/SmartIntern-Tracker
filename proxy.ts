import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Next.js 16 Proxy (replaces middleware.ts).
 *
 * Protected routes — redirect to /login if no access_token cookie is present.
 * Public routes — redirect to /dashboard if user is already logged in.
 *
 * NOTE: We read the token from cookies (set during login/signup).
 *       localStorage is not available in Edge proxy, so the cookie
 *       is the source of truth for the proxy layer.
 */

const PROTECTED_PREFIXES = [
  '/dashboard',
  '/profile',
  '/applications',
  '/resume',
  '/settings',
  '/jobs',
  '/assistant',
  '/cold-email',
  '/automation',
]

const AUTH_PAGES = ['/login', '/signup']

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const token = request.cookies.get('access_token')?.value

  const isProtected = PROTECTED_PREFIXES.some((prefix) =>
    pathname.startsWith(prefix)
  )
  const isAuthPage = AUTH_PAGES.some((page) => pathname.startsWith(page))

  // Redirect unauthenticated users away from protected pages
  if (isProtected && !token) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('next', pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Redirect authenticated users away from login/signup (they're already in)
  if (isAuthPage && token) {
    const next = request.nextUrl.searchParams.get('next') || '/dashboard'
    return NextResponse.redirect(new URL(next, request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths EXCEPT:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico, public assets
     * - api routes (backend handles its own auth)
     */
    '/((?!_next/static|_next/image|favicon|public|static|api/).*)',
  ],
}
