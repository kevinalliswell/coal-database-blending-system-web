const EVENT_KEY = 'cbos_session_changed';

/** Publish only a random wake-up marker; cookies and CSRF tokens stay out of storage. */
export function createSessionNotifier(onChange: () => void) {
  if (typeof BroadcastChannel === 'function') {
    const channel = new BroadcastChannel(EVENT_KEY);
    channel.onmessage = () => onChange();
    return { notify: () => channel.postMessage(crypto.randomUUID()), close: () => channel.close() };
  }
  const listener = (event: StorageEvent) => { if (event.key === EVENT_KEY && event.newValue) onChange(); };
  window.addEventListener('storage', listener);
  return {
    notify: () => { try { localStorage.setItem(EVENT_KEY, crypto.randomUUID()); } catch { /* Read headers still enforce session identity. */ } },
    close: () => window.removeEventListener('storage', listener),
  };
}
