import { create } from 'zustand';

interface BookingConstraints {
  maxPrice: number | null;
  preferredDate: string | null;
  serviceType: string | null;
}

export interface LogEvent {
  timestamp: string;
  status: string;
  payload?: any;
}

interface AppState {
  isDarkMode: boolean;
  toggleDarkMode: () => void;
  bookingConstraints: BookingConstraints;
  setBookingConstraints: (constraints: Partial<BookingConstraints>) => void;
  
  // Phase 4: WebSocket State
  clientId: string;
  isConnected: boolean;
  setConnectionStatus: (status: boolean) => void;
  logs: LogEvent[];
  addLog: (log: LogEvent) => void;
  clearLogs: () => void;
  finalDecision: any | null;
  setFinalDecision: (decision: any) => void;
}

// Generate a random client ID once per session
const generateClientId = () => `client_${Math.random().toString(36).substring(2, 10)}`;

export const useStore = create<AppState>((set) => ({
  isDarkMode: true,
  toggleDarkMode: () => set((state) => ({ isDarkMode: !state.isDarkMode })),
  bookingConstraints: {
    maxPrice: null,
    preferredDate: null,
    serviceType: null,
  },
  setBookingConstraints: (constraints) =>
    set((state) => ({
      bookingConstraints: { ...state.bookingConstraints, ...constraints },
    })),
    
  // Phase 4 initial state
  clientId: generateClientId(),
  isConnected: false,
  setConnectionStatus: (status) => set({ isConnected: status }),
  logs: [],
  addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),
  clearLogs: () => set({ logs: [], finalDecision: null }),
  finalDecision: null,
  setFinalDecision: (decision) => set({ finalDecision: decision }),
}));
