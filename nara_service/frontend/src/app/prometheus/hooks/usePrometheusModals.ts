import { useState, useCallback } from 'react';

export type ModalType = 'login' | 'chat' | 'save' | 'load' | 'hierarchy' | 'link';

interface UsePrometheusModalsReturn {
  openModals: Set<ModalType>;
  isOpen: (modal: ModalType) => boolean;
  openModal: (modal: ModalType) => void;
  closeModal: (modal: ModalType) => void;
  toggleModal: (modal: ModalType) => void;
}

/**
 * Centralized modal state management for Prometheus page
 *
 * Consolidates 6 modal states (login, chat, save, load, hierarchy, link)
 * into a single hook for cleaner state management and reduced prop drilling.
 */
export const usePrometheusModals = (): UsePrometheusModalsReturn => {
  const [openModals, setOpenModals] = useState<Set<ModalType>>(new Set());

  const isOpen = useCallback(
    (modal: ModalType): boolean => openModals.has(modal),
    [openModals]
  );

  const openModal = useCallback((modal: ModalType) => {
    setOpenModals((prev) => {
      const next = new Set(prev);
      next.add(modal);
      return next;
    });
  }, []);

  const closeModal = useCallback((modal: ModalType) => {
    setOpenModals((prev) => {
      const next = new Set(prev);
      next.delete(modal);
      return next;
    });
  }, []);

  const toggleModal = useCallback((modal: ModalType) => {
    setOpenModals((prev) => {
      const next = new Set(prev);
      if (next.has(modal)) {
        next.delete(modal);
      } else {
        next.add(modal);
      }
      return next;
    });
  }, []);

  return {
    openModals,
    isOpen,
    openModal,
    closeModal,
    toggleModal,
  };
};
