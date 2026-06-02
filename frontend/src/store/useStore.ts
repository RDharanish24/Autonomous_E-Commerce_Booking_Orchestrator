import { create } from 'zustand';

interface BookingConstraints {
  maxPrice: number | null;
  preferredDate: string | null;
  serviceType: string | null;
}

interface AppState {
  isDarkMode: boolean;
  toggleDarkMode: () => void;
  bookingConstraints: BookingConstraints;
  setBookingConstraints: (constraints: Partial<BookingConstraints>) => void;
}

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
}));
