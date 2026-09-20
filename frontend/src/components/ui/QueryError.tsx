import { Icon } from './Icon';

export function QueryError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="empty" role="alert">
    <Icon name="alert" size={24} />
    <h3>{message}</h3>
    <p className="text-mute">请检查服务连接后重试。</p>
    <button className="btn btn--ghost" onClick={onRetry}>重新加载</button>
  </div>;
}
