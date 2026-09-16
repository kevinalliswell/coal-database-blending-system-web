const APP_ORIGIN = 'cbos://app';
const CONTENT_SECURITY_POLICY = [
  "default-src 'self'", "script-src 'self'", "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:", "font-src 'self'", "connect-src 'self'",
  "object-src 'none'", "frame-src 'none'", "base-uri 'none'", "form-action 'none'",
].join('; ');

function isAppUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'cbos:' && url.hostname === 'app' && !url.port && !url.username && !url.password;
  } catch { return false; }
}
function isDownloadUrl(value) {
  return isAppUrl(value) || (value.startsWith('blob:') && isAppUrl(value.slice(5)));
}

// A stable origin keeps theme/settings across launches; the random loopback port
// and per-launch credential stay in the main process, outside the renderer.
async function proxyRequest(request, backend) {
  if (!isAppUrl(request.url)) return new Response('Forbidden', { status: 403 });
  const url = new URL(request.url);
  const headers = new Headers({ 'X-CBOS-Token': backend.token });
  for (const name of ['accept', 'content-type']) {
    if (request.headers.has(name)) headers.set(name, request.headers.get(name));
  }
  const hasBody = !['GET', 'HEAD'].includes(request.method);
  const upstream = await fetch(backend.origin + url.pathname + url.search, {
    method: request.method, headers, body: hasBody ? request.body : undefined,
    ...(hasBody ? { duplex: 'half' } : {}), signal: request.signal, redirect: 'error',
  });
  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete('access-control-allow-origin');
  responseHeaders.delete('x-cbos-token');
  responseHeaders.set('Content-Security-Policy', CONTENT_SECURITY_POLICY);
  responseHeaders.set('X-Content-Type-Options', 'nosniff');
  responseHeaders.set('Referrer-Policy', 'no-referrer');
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}
module.exports = { APP_ORIGIN, CONTENT_SECURITY_POLICY, isAppUrl, isDownloadUrl, proxyRequest };
