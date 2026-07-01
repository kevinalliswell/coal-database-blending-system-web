import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export const qk = {
  health: ['health'] as const,
  coals: (q: unknown) => ['coals', q] as const,
  coal: (id: number) => ['coal', id] as const,
  coalTypes: ['coalTypes'] as const,
  optHistory: ['optHistory'] as const,
  optHistoryDetail: (id: number) => ['optHistory', id] as const,
  repHistory: ['repHistory'] as const,
  repHistoryDetail: (id: number) => ['repHistory', id] as const,
};
