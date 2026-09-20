const EVENT_KEY = 'cbos_session_changed';
let sequence = 0;
// This is a wake-up marker, not an authentication secret. It must also work
// without secure-context crypto APIs and change on every storage write.
const wakeupMarker = () => `${Date.now()}-${++sequence}-${Math.random()}`;

/** Publish only a random wake-up marker; cookies and CSRF tokens stay out of storage. */
export function createSessionNotifier(onChange: () => void) {
  if (typeof BroadcastChannel === 'function') {
    const channel = new BroadcastChannel(EVENT_KEY);
    channel.onmessage = () => onChange();
    return { notify: () => channel.postMessage(wakeupMarker()), close: () => channel.close() };
  }
  const listener = (event: StorageEvent) => { if (event.key === EVENT_KEY && event.newValue) onChange(); };
  window.addEventListener('storage', listener);
  return {
    notify: () => { try { localStorage.setItem(EVENT_KEY, wakeupMarker()); } catch { /* Read headers still enforce session identity. */ } },
    close: () => window.removeEventListener('storage', listener),
  };
}
